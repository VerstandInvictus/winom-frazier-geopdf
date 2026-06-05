"""Build a north-up SVG overlay for the 2025 guide page 1 (Desolation OHV map).

Reads config/desolation_transform.json (the picker's pixel->lon/lat affine) and writes:
  viewer/desolation.svg            — north-up, geo-aligned vector overlay (clipped to the neatline)
  viewer/desolation_overlay.json   — {bounds:[[minLat,minLon],[maxLat,maxLon]]}

The Desolation map is the top-right panel of page 0 (printed rotated ~180deg); the affine
encodes that rotation, so the overlay comes out north-up. The neatline is the printed map
border (clicked in viewer/pick_desolation.html).
"""
import json
import re
from pathlib import Path
import fitz

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "2025_WinomFrazierDesolationGuide.pdf"
PAGE = 0
T = json.loads((ROOT / "config" / "desolation_transform.json").read_text())
af = T["affine_px_to_lonlat"]
a, b, c, d, e, f = af["a"], af["b"], af["c"], af["d"], af["e"], af["f"]
SCALE = T["dpi"] / 72.0  # render-px per PDF-point

# Map neatline (render px) — printed border corners, clockwise from top-left (clicked).
NEATLINE_CORNERS = [(3868, 154), (6152, 152), (6150, 1898), (3870, 1898)]


def build_svg(out_svg, out_json):
    # neatline corners -> lon/lat -> crop extent for the viewBox + bounds
    nb_lonlat = [(a * px + b * py + c, d * px + e * py + f) for px, py in NEATLINE_CORNERS]
    lons = [p[0] for p in nb_lonlat]
    lats = [p[1] for p in nb_lonlat]
    minlon, maxlon, minlat, maxlat = min(lons), max(lons), min(lats), max(lats)
    # page svg coords (sx,sy; y-down points) -> overlay coords (ux=lon, uy=-lat):
    A, C, E = a * SCALE, b * SCALE, c
    B, D, F = -(d * SCALE), -(e * SCALE), -f
    doc = fitz.open(str(SRC))
    page = doc[PAGE]
    svg = page.get_svg_image()
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, count=1, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    # clip to the neatline: its render-px corners -> overlay coords (lon, -lat)
    poly = " ".join(f"{a*px + b*py + c},{-(d*px + e*py + f)}" for px, py in NEATLINE_CORNERS)
    vb = f"{minlon} {-maxlat} {maxlon - minlon} {maxlat - minlat}"
    wrapped = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="{vb}" preserveAspectRatio="none">'
        f'<defs><clipPath id="neat" clipPathUnits="userSpaceOnUse">'
        f'<polygon points="{poly}"/></clipPath></defs>'
        f'<g clip-path="url(#neat)"><g transform="matrix({A} {B} {C} {D} {E} {F})">{inner}</g></g>'
        "</svg>"
    )
    Path(out_svg).write_text(wrapped, encoding="utf-8")
    Path(out_json).write_text(json.dumps({"bounds": [[minlat, minlon], [maxlat, maxlon]]}))
    return len(wrapped), {"bounds": [[minlat, minlon], [maxlat, maxlon]]}


if __name__ == "__main__":
    n, ov = build_svg(ROOT / "viewer" / "desolation.svg", ROOT / "viewer" / "desolation_overlay.json")
    print(f"desolation.svg ({n} bytes)")
    print("overlay:", json.dumps(ov))
