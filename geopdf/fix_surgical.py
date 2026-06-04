"""Fix: collapse a multi-viewport GeoPDF to a single authoritative viewport."""
from __future__ import annotations
from pathlib import Path
import pikepdf

from geopdf.pdfgeo import _clean_name


def collapse_to_single_viewport(in_path, out_path, keep_name: str) -> int:
    """Rewrite each page's /VP array to keep only viewports named keep_name.

    Non-destructive: reads in_path, writes out_path. Map content is untouched
    (only the /VP viewport array changes), so the map renders identically.
    Returns the number of viewports kept. Raises ValueError if none match.
    """
    with pikepdf.open(str(in_path)) as pdf:
        kept_total = 0
        for page in pdf.pages:
            pageobj = getattr(page, "obj", page)
            vp = pageobj.get("/VP")
            if vp is None:
                continue
            keep = [v for v in vp if _clean_name(v.get("/Name")) == keep_name]
            if keep:
                pageobj["/VP"] = pikepdf.Array(keep)
                kept_total += len(keep)
        if kept_total == 0:
            raise ValueError(f"no viewport named {keep_name!r} found in {in_path}")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out_path))
    return kept_total
