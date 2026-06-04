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


def main():
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("decode").set_defaults(func=cmd_decode)
    sub.add_parser("report").set_defaults(func=cmd_report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
