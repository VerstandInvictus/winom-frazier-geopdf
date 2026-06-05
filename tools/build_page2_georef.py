"""Build a vector GeoPDF + north-up SVG overlay for 2025 guide page 2.

Reads config/page2_transform.json (the picker's pixel->lon/lat affine) and writes:
  output/2025_WinomFrazier_page2_georef.pdf   — vector GeoPDF (page 2, /VP added)
  viewer/page2.svg                            — north-up, geo-aligned vector overlay
  viewer/page2_overlay.json                   — {bounds:[[minLat,minLon],[maxLat,maxLon]]}
"""
import json
import re
from pathlib import Path
import fitz
import pikepdf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "2025_WinomFrazierDesolationGuide.pdf"
PAGE = 1
T = json.loads((ROOT / "config" / "page2_transform.json").read_text())
af = T["affine_px_to_lonlat"]
a, b, c, d, e, f = af["a"], af["b"], af["c"], af["d"], af["e"], af["f"]
corners = T["corners_lonlat"]              # image corners (0,0),(W,0),(W,H),(0,H) -> [lon,lat]
W, H = T["image_size"]
SCALE = T["dpi"] / 72.0                     # render-px per PDF-point

WGS84_WKT = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
             'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]')

# Neatline of the main map (render px, original orientation) — crop excluding title + legend.
NEATLINE_PX = (2004, 376, 5769, 4080)


def build_geopdf(out):
    UL, UR, LR, LL = corners[0], corners[1], corners[2], corners[3]
    ll = lambda p: [p[1], p[0]]            # [lon,lat] -> [lat,lon]
    gpts = ll(UL) + ll(LL) + ll(LR) + ll(UR)   # LPTS order [0 1 0 0 1 0 1 1]: UL,LL,LR,UR
    with pikepdf.open(str(SRC)) as pdf:
        page = pdf.pages[PAGE]
        pageobj = getattr(page, "obj", page)
        x0, y0, x1, y1 = [float(v) for v in pageobj.MediaBox]
        gcs = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/GEOGCS"), WKT=pikepdf.String(WGS84_WKT)))
        measure = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/Measure"), Subtype=pikepdf.Name("/GEO"),
            GPTS=pikepdf.Array([float(v) for v in gpts]),
            LPTS=pikepdf.Array([0, 1, 0, 0, 1, 0, 1, 1]),
            GCS=gcs))
        vp = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/Viewport"),
            BBox=pikepdf.Array([x0, y0, x1, y1]),
            Name=pikepdf.String("Winom-Frazier 2025 page2"),
            Measure=measure))
        pageobj["/VP"] = pikepdf.Array([vp])
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out))
    return out


def build_svg(out_svg, out_json):
    # Crop extent = the map neatline (render-px) -> lon/lat, so the viewBox + bounds frame just
    # the cropped map; title/legend outside the neatline are clipped away.
    nb = NEATLINE_PX
    pxc = [(nb[0], nb[1]), (nb[2], nb[1]), (nb[2], nb[3]), (nb[0], nb[3])]
    nb_lonlat = [(a * px + b * py + c, d * px + e * py + f) for px, py in pxc]
    lons = [p[0] for p in nb_lonlat]
    lats = [p[1] for p in nb_lonlat]
    minlon, maxlon, minlat, maxlat = min(lons), max(lons), min(lats), max(lats)
    # page svg coords (sx,sy; y-down points) -> overlay coords (ux=lon, uy=-lat):
    #   lon = a*SCALE*sx + b*SCALE*sy + c ;  lat = d*SCALE*sx + e*SCALE*sy + f
    A, C, E = a * SCALE, b * SCALE, c
    B, D, F = -(d * SCALE), -(e * SCALE), -f
    doc = fitz.open(str(SRC))
    page = doc[PAGE]
    svg = page.get_svg_image()
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, count=1, flags=re.S)
    inner = re.sub(r"</svg>\s*$", "", inner, flags=re.S)
    # clip to the map neatline: its 4 render-px corners -> overlay coords (lon, -lat)
    poly = " ".join(f"{a*px + b*py + c},{-(d*px + e*py + f)}" for px, py in pxc)
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
    return out_svg, len(wrapped)


if __name__ == "__main__":
    pdf_out = build_geopdf(ROOT / "output" / "2025_WinomFrazier_page2_georef.pdf")
    print(f"GeoPDF -> {pdf_out}")
    # verify the viewport round-trips
    import sys
    sys.path.insert(0, str(ROOT))
    from geopdf.pdfgeo import decode_pdf
    vps = decode_pdf(pdf_out).viewports
    for vp in vps:
        print(f"  viewport '{vp.name}': center={vp.bounds.center} area_km2={vp.bounds.area_km2:.0f}")
    svg_out, n = build_svg(ROOT / "viewer" / "page2.svg", ROOT / "viewer" / "page2_overlay.json")
    print(f"SVG overlay -> {svg_out} ({n} bytes)")
