"""Cross-file comparison report for the trail-map PDFs."""
from __future__ import annotations
from pathlib import Path
import pikepdf
from geopdf.pdfgeo import decode_pdf, scan_all_gpts


def _flag(area_km2: float) -> str:
    if area_km2 < 1:
        return "inset-scale"
    if area_km2 > 50_000:
        return "locator-scale"
    return "trail-scale"


def _metadata(path) -> dict:
    with pikepdf.open(str(path)) as pdf:
        info = pdf.docinfo

        def g(k):
            return str(info[k]) if k in info else ""

        return {
            "pages": len(pdf.pages),
            "creator": g("/Creator"),
            "producer": g("/Producer"),
            "created": g("/CreationDate"),
            "modified": g("/ModDate"),
        }


def build_report(paths) -> list[dict]:
    records = []
    for path in paths:
        path = Path(path)
        record = {"filename": path.name}
        try:
            record["metadata"] = _metadata(path)
            decoded = decode_pdf(path)
            all_boxes = scan_all_gpts(path)
        except Exception as exc:  # surface unreadable files instead of crashing
            record.update({"error": str(exc), "georeferenced": False,
                           "viewport_count": 0, "viewports": [], "embedded_gpts_boxes": 0})
            records.append(record)
            continue
        vps = []
        for vp in decoded.viewports:
            w, h = vp.bounds.span_km
            vps.append({
                "name": vp.name,
                "center": [round(vp.bounds.center[0], 5), round(vp.bounds.center[1], 5)],
                "area_km2": round(vp.bounds.area_km2, 3),
                "span_km": [round(w, 2), round(h, 2)],
                "crs": vp.crs_name,
                "flag": _flag(vp.bounds.area_km2),
            })
        record.update({
            "georeferenced": len(decoded.viewports) > 0,
            "viewport_count": len(decoded.viewports),
            "viewports": vps,
            "embedded_gpts_boxes": len(all_boxes),
        })
        records.append(record)
    return records


def render_markdown(report) -> str:
    lines = ["## File summary\n",
             "| File | Pages | Creator/Producer | Created | Modified | Georeferenced | Viewports |",
             "|---|---|---|---|---|---|---|"]
    for r in report:
        m = r.get("metadata", {})
        geo = "yes" if r.get("georeferenced") else "**NO**"
        creator = m.get("creator") or m.get("producer", "")
        lines.append(f"| {r['filename']} | {m.get('pages','?')} | {creator} | "
                     f"{m.get('created','')} | {m.get('modified','')} | {geo} | {r.get('viewport_count',0)} |")
    lines += ["\n## Viewports\n",
              "| File | Viewport | Center (lat,lon) | Area km² | Span km | Flag |",
              "|---|---|---|---|---|---|"]
    for r in report:
        if not r.get("viewports"):
            lines.append(f"| {r['filename']} | (none) | - | - | - | not georeferenced |")
        for vp in r["viewports"]:
            lines.append(f"| {r['filename']} | {vp['name']} | {vp['center'][0]}, {vp['center'][1]} | "
                         f"{vp['area_km2']} | {vp['span_km'][0]}×{vp['span_km'][1]} | {vp['flag']} |")
    return "\n".join(lines)
