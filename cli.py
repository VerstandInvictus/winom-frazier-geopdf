"""Thin CLI dispatch for the geopdf toolkit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PDFS = [
    PROJECT_ROOT / "2025_WinomFrazierDesolationGuide.pdf",
    PROJECT_ROOT / "Winom-Frazier OHV.pdf",
    PROJECT_ROOT / "Winom-Frazier OHV_260503_142151.pdf",
]
OUTPUT = PROJECT_ROOT / "output"
VIEWER = PROJECT_ROOT / "viewer"


def cmd_decode(_args):
    from geopdf.pdfgeo import decode_pdf, scan_all_gpts
    for p in DEFAULT_PDFS:
        d = decode_pdf(p)
        print(f"\n=== {p.name} ===  viewports: {len(d.viewports)}  "
              f"embedded boxes: {len(scan_all_gpts(p))}")
        for vp in d.viewports:
            print(f"  {vp.name:28} center={vp.bounds.center} "
                  f"area_km2={vp.bounds.area_km2:.2f} crs={vp.crs_name}")


def cmd_report(_args):
    from geopdf.report import build_report, render_markdown
    report = build_report(DEFAULT_PDFS)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "bounds_report.json").write_text(json.dumps(report, indent=2))
    md = render_markdown(report)
    (OUTPUT / "bounds_report.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\nWrote {OUTPUT / 'bounds_report.json'} and {OUTPUT / 'bounds_report.md'}")


def cmd_diagnose(_args):
    from geopdf.diagnose import diagnose, load_known_points, write_findings
    points = load_known_points(PROJECT_ROOT / "config" / "known_points.json")
    if not points:
        print("NOTE: config/known_points.json not found/empty — structural diagnosis only "
              "(coordinates are an optional independent confirmation).")
    result = diagnose(DEFAULT_PDFS, points)
    findings = PROJECT_ROOT / "docs" / "superpowers" / "specs" / "2026-06-03-winom-frazier-FINDINGS.md"
    findings.parent.mkdir(parents=True, exist_ok=True)
    write_findings(result, findings)
    print(f"Decision: {result['decision']}")
    for f in result["files"]:
        print(f"  {f['filename']}: georef={f['georeferenced']} main={f['main_map_name']}")
    print(f"Wrote {findings}")


def cmd_fix(_args):
    from geopdf.fix_surgical import collapse_to_single_viewport
    from geopdf.pdfgeo import decode_pdf
    src = PROJECT_ROOT / "Winom-Frazier OHV.pdf"   # the 2016 Adobe original
    out = OUTPUT / "Winom-Frazier OHV_corrected.pdf"
    OUTPUT.mkdir(exist_ok=True)
    n = collapse_to_single_viewport(src, out, keep_name="Winom-FrazierData")
    vp = decode_pdf(out).viewports[0]
    print(f"Collapsed {src.name}: kept {n} viewport -> {out}")
    print(f"  remaining viewport: {vp.name}  area_km2={vp.bounds.area_km2:.1f}  center={vp.bounds.center}")


def cmd_export(_args):
    from geopdf.pdfgeo import decode_pdf
    from geopdf.render import render_page_png, page_height_pts
    from geopdf.raster import corners_to_gcps, write_geotiff
    corrected = OUTPUT / "Winom-Frazier OHV_corrected.pdf"
    src = corrected if corrected.exists() else (PROJECT_ROOT / "Winom-Frazier OHV.pdf")
    decoded = decode_pdf(src)
    vp = next(v for v in decoded.viewports if v.name == "Winom-FrazierData")
    x0, y0, x1, y1 = vp.bbox
    H = page_height_pts(src, vp.page_index)
    # PDF y-up -> pymupdf y-down; normalize so that clip_y0 < clip_y1
    cy0, cy1 = H - y1, H - y0
    clip = (min(x0, x1), min(cy0, cy1), max(x0, x1), max(cy0, cy1))
    OUTPUT.mkdir(exist_ok=True)
    png, w, h = render_page_png(src, OUTPUT / "map.png", vp.page_index, dpi=200, clip=clip)
    gcps = corners_to_gcps(vp.gpts, w, h)
    out = write_geotiff(png, gcps, VIEWER / "winom-frazier_corrected.tif")
    print(f"Rendered main map clip {w}x{h}px -> {png}")
    print(f"Wrote GeoTIFF -> {out}")


def cmd_render_guide(_args):
    from geopdf.render import render_page_png
    src = PROJECT_ROOT / "2025_WinomFrazierDesolationGuide.pdf"
    OUTPUT.mkdir(exist_ok=True)
    for i in range(2):
        png, w, h = render_page_png(src, OUTPUT / f"guide_page{i + 1}.png", page_index=i, dpi=150)
        print(f"Wrote {png} ({w}x{h}px)")


def main():
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("decode").set_defaults(func=cmd_decode)
    sub.add_parser("report").set_defaults(func=cmd_report)
    sub.add_parser("diagnose").set_defaults(func=cmd_diagnose)
    sub.add_parser("fix").set_defaults(func=cmd_fix)
    sub.add_parser("export").set_defaults(func=cmd_export)
    sub.add_parser("render-guide").set_defaults(func=cmd_render_guide)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
