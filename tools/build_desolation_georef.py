"""Build a rotated raster overlay for the 2025 guide page 0 (Desolation OHV map).

The Desolation map's topo base is embedded CMYK JPEGs, which render dark inside an SVG
overlay. fitz's pixmap renderer converts CMYK correctly, so we use a RASTER overlay (like
the 2016 map): crop the rendered page to the neatline and place it via L.imageOverlay.rotated
using the neatline's geo corners (the affine encodes the ~180deg print rotation -> north-up).

Reads config/desolation_transform.json and output/guide_desolation_hi.png; writes:
  viewer/desolation.webp           — cropped Desolation map (rotated-print orientation)
  viewer/desolation_overlay.json   — {topleft,topright,bottomleft} geo corners ([lat,lon])
"""
import json
from pathlib import Path
from PIL import Image
import pikepdf

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "2025_WinomFrazierDesolationGuide.pdf"
WGS84_WKT = ('GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
             'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]')
T = json.loads((ROOT / "config" / "desolation_transform.json").read_text())
af = T["affine_px_to_lonlat"]
a, b, c, d, e, f = af["a"], af["b"], af["c"], af["d"], af["e"], af["f"]

# Neatline bbox in 200-dpi render px (the printed map border the user clicked, axis-aligned).
CROP = (3868, 152, 6152, 1898)


def latlon(px, py):
    return [d * px + e * py + f, a * px + b * py + c]  # [lat, lon]


def build(out_webp, out_json):
    im = Image.open(ROOT / "output" / "guide_desolation_hi.png").convert("RGB")
    crop = im.crop(CROP)
    crop.save(out_webp, "WEBP", quality=82, method=6)
    x0, y0, x1, y1 = CROP
    overlay = {
        "topleft": latlon(x0, y0),       # img TL  -> geo
        "topright": latlon(x1, y0),      # img TR  -> geo
        "bottomleft": latlon(x0, y1),    # img BL  -> geo
    }
    Path(out_json).write_text(json.dumps(overlay))
    return crop.size, overlay


def build_geopdf(out):
    """Add a /VP over the Desolation map panel of page 0 (geo-registered GeoPDF)."""
    SCALE = T["dpi"] / 72.0
    x0r, y0r, x1r, y1r = CROP  # render px (200 dpi), y-down
    # neatline corners -> geo [lat,lon] in LPTS order [0,1, 0,0, 1,0, 1,1] = TL, BL, BR, TR
    gpts = latlon(x0r, y0r) + latlon(x0r, y1r) + latlon(x1r, y1r) + latlon(x1r, y0r)
    with pikepdf.open(str(SRC)) as pdf:
        page = pdf.pages[0]
        pageobj = getattr(page, "obj", page)
        mb = [float(v) for v in pageobj.MediaBox]
        ph = mb[3] - mb[1]  # page height (pt); flip render y-down -> PDF y-up
        bbox = [x0r / SCALE, ph - y1r / SCALE, x1r / SCALE, ph - y0r / SCALE]
        gcs = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/GEOGCS"), WKT=pikepdf.String(WGS84_WKT)))
        measure = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/Measure"), Subtype=pikepdf.Name("/GEO"),
            GPTS=pikepdf.Array([float(v) for v in gpts]),
            LPTS=pikepdf.Array([0, 1, 0, 0, 1, 0, 1, 1]), GCS=gcs))
        vp = pdf.make_indirect(pikepdf.Dictionary(
            Type=pikepdf.Name("/Viewport"), BBox=pikepdf.Array([float(v) for v in bbox]),
            Name=pikepdf.String("Desolation OHV map"), Measure=measure))
        pageobj["/VP"] = pikepdf.Array([vp])
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out))
    return out


if __name__ == "__main__":
    size, ov = build(ROOT / "viewer" / "desolation.webp", ROOT / "viewer" / "desolation_overlay.json")
    print(f"desolation.webp {size}")
    print("overlay:", json.dumps(ov))
    pdf_out = build_geopdf(ROOT / "output" / "Desolation_OHV_georef.pdf")
    print(f"GeoPDF -> {pdf_out}")
    import sys
    sys.path.insert(0, str(ROOT))
    from geopdf.pdfgeo import decode_pdf
    for vp in decode_pdf(pdf_out).viewports:
        print(f"  viewport '{vp.name}': center={vp.bounds.center} area_km2={vp.bounds.area_km2:.0f}")
