"""Rasterize PDF pages to PNG via pymupdf (fitz)."""
from __future__ import annotations
from pathlib import Path
import fitz


def render_page_png(pdf_path, out_png, page_index: int = 0, dpi: int = 200, clip=None):
    """Render a page (or a clip region) to PNG. Returns (Path, width_px, height_px).

    clip, if given, is (x0, y0, x1, y1) in pymupdf page coordinates (y-down).
    """
    doc = fitz.open(str(pdf_path))
    page = doc[page_index]
    kwargs = {"dpi": dpi}
    if clip is not None:
        kwargs["clip"] = fitz.Rect(*clip)
    pix = page.get_pixmap(**kwargs)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))
    w, h = pix.width, pix.height
    doc.close()
    return Path(out_png), w, h


def page_height_pts(pdf_path, page_index: int = 0) -> float:
    """Page height in PDF points (for converting PDF y-up BBox to pymupdf y-down clip)."""
    doc = fitz.open(str(pdf_path))
    h = doc[page_index].rect.height
    doc.close()
    return h
