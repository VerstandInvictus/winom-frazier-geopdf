"""Structural read of geospatial PDFs via pikepdf."""
from __future__ import annotations
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import pikepdf

from geopdf.crs import Bounds, bounds_from_gpts, crs_name_from_wkt


@dataclass
class Viewport:
    page_index: int
    index: int
    name: str
    bbox: list[float]
    bbox_area: float
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


def _clean_name(name) -> str:
    if name is None:
        return ""
    return str(name).replace("\x00", "").strip()


def _bbox_area(bbox: list[float]) -> float:
    if len(bbox) < 4:
        return 0.0
    return abs((bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))


def decode_pdf(path) -> DecodeResult:
    """Read the page /VP viewports in document order (no reordering).

    All viewports are returned faithfully with their /Name and page-space /BBox
    so callers can distinguish the main map from inset/locator viewports.
    """
    result = DecodeResult(path=str(path))
    with pikepdf.open(str(path)) as pdf:
        for pi, page in enumerate(pdf.pages):
            pageobj = getattr(page, "obj", page)
            vp = pageobj.get("/VP")
            if vp is None:
                continue
            for vi, viewport in enumerate(vp):
                measure = viewport.get("/Measure")
                if measure is None:
                    continue
                gpts = measure.get("/GPTS")
                if gpts is None:
                    continue
                gcs = measure.get("/GCS")
                wkt = str(gcs["/WKT"]) if gcs is not None and "/WKT" in gcs else None
                raw_bbox = viewport.get("/BBox")
                bbox = _floats(raw_bbox) if raw_bbox is not None else []
                gpts_f = _floats(gpts)
                result.viewports.append(Viewport(
                    page_index=pi,
                    index=vi,
                    name=_clean_name(viewport.get("/Name")),
                    bbox=bbox,
                    bbox_area=_bbox_area(bbox),
                    bounds=bounds_from_gpts(gpts_f),
                    crs_name=crs_name_from_wkt(wkt),
                    wkt=wkt,
                    gpts=gpts_f,
                ))
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
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp_path = tmp.name
            with pikepdf.open(str(path)) as pdf:
                pdf.save(tmp_path, compress_streams=False,
                         object_stream_mode=pikepdf.ObjectStreamMode.disable)
            matches = _GPTS_RE.findall(Path(tmp_path).read_bytes())
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
    boxes: list[Bounds] = []
    for raw in matches:
        nums = [float(x) for x in raw.split()]
        if len(nums) >= 8:
            boxes.append(bounds_from_gpts(nums[:8]))
    return boxes
