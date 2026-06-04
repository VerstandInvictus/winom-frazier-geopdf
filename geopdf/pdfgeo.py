"""Structural read of geospatial PDFs via pikepdf."""
from __future__ import annotations
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import pikepdf

from geopdf.crs import Bounds, bounds_from_gpts, crs_name_from_wkt


@dataclass
class Viewport:
    page_index: int
    bbox: list[float]
    bounds: Bounds
    crs_name: str
    wkt: str | None
    gpts: list[float]


@dataclass
class DecodeResult:
    path: str
    viewports: list[Viewport] = field(default_factory=list)


def _floats(arr) -> list[float]:
    return [float(x) for x in arr]


def _measure_to_viewport(page_index: int, bbox, measure) -> Viewport | None:
    gpts = measure.get("/GPTS")
    if gpts is None:
        return None
    gcs = measure.get("/GCS")
    wkt = None
    if gcs is not None and "/WKT" in gcs:
        wkt = str(gcs["/WKT"])
    gpts_f = _floats(gpts)
    return Viewport(
        page_index=page_index,
        bbox=_floats(bbox) if bbox is not None else [],
        bounds=bounds_from_gpts(gpts_f),
        crs_name=crs_name_from_wkt(wkt),
        wkt=wkt,
        gpts=gpts_f,
    )


def decode_pdf(path) -> DecodeResult:
    """Read the page /VP viewports.

    Returns viewports in GPS-priority order: the *last* viewport in the /VP
    array comes first.  GPS apps (e.g. Avenza Maps) resolve georeferencing by
    taking the final entry in the /VP array as the authoritative reference —
    which is what produces the "wrong tiny inset" bug in ohv_single.  Returning
    it at index 0 makes the primary GPS viewport directly accessible as
    ``result.viewports[0]`` while preserving the full list for forensic work.
    """
    result = DecodeResult(path=str(path))
    with pikepdf.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            pageobj = getattr(page, "obj", page)
            vp = pageobj.get("/VP")
            if vp is None:
                continue
            page_viewports: list[Viewport] = []
            for viewport in vp:
                measure = viewport.get("/Measure")
                if measure is None:
                    continue
                v = _measure_to_viewport(i, viewport.get("/BBox"), measure)
                if v is not None:
                    page_viewports.append(v)
            # Reverse so that the last /VP entry (GPS-primary) is at index 0.
            result.viewports.extend(reversed(page_viewports))
    return result


_GPTS_RE = re.compile(rb"/GPTS\s*\[([^\]]+)\]")


def scan_all_gpts(path) -> list[Bounds]:
    """Forensic scan: every embedded GPTS box, including orphaned inset boxes.

    Reads raw bytes first; if no hits (streams compressed), saves a
    decompressed copy and rescans.
    """
    data = Path(path).read_bytes()
    matches = _GPTS_RE.findall(data)
    if not matches:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        with pikepdf.open(str(path)) as pdf:
            pdf.save(tmp_path, compress_streams=False,
                     object_stream_mode=pikepdf.ObjectStreamMode.disable)
        matches = _GPTS_RE.findall(Path(tmp_path).read_bytes())
    boxes: list[Bounds] = []
    for raw in matches:
        nums = [float(x) for x in raw.split()]
        if len(nums) >= 8:
            boxes.append(bounds_from_gpts(nums[:8]))
    return boxes
