"""Build a rotated raster overlay for heppner ohv.pdf page 1 (already geocoded).

Page 0 carries an embedded /VP viewport (NAD83 Oregon North State Plane GCS, GPTS in lat/lon),
so we read the corners straight from the PDF -- no control-point picking. Renders the page,
crops to the viewport bbox, and writes a rotated-raster overlay like the Desolation map (its
topo base is CMYK rasters that render dark as SVG, so raster it is).

Writes: viewer/heppner.webp, viewer/heppner_overlay.json {topleft,topright,bottomleft} [lat,lon]
"""
import json
from pathlib import Path
import pikepdf
import fitz
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "heppner ohv.pdf"
PAGE = 0
DPI = 200
SCALE = DPI / 72.0


def build(out_webp, out_json):
    pdf = pikepdf.open(str(SRC))
    obj = pdf.pages[PAGE].obj
    ph = float(obj.MediaBox[3])
    vp = obj.VP[0]
    bx = [float(x) for x in vp.BBox]
    gpts = [float(x) for x in vp.Measure.GPTS]  # lat,lon pairs, LPTS order [0,1, 0,0, 1,0, 1,1]
    pdf.close()
    x_left, x_right = min(bx[0], bx[2]), max(bx[0], bx[2])
    y_bot, y_top = min(bx[1], bx[3]), max(bx[1], bx[3])  # PDF points, y-up

    # render full page, crop to the viewport bbox (render px, y-down from top)
    fitz.open(str(SRC))[PAGE].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE)).save(ROOT / "output" / "heppner_hi.png")
    img = Image.open(ROOT / "output" / "heppner_hi.png").convert("RGB")
    crop = (round(x_left * SCALE), round((ph - y_top) * SCALE),
            round(x_right * SCALE), round((ph - y_bot) * SCALE))
    img.crop(crop).save(out_webp, "WEBP", quality=82, method=6)

    # LPTS [0,1]=TL, [0,0]=BL, [1,0]=BR, [1,1]=TR -> GPTS pairs
    overlay = {"topleft": gpts[0:2], "topright": gpts[6:8], "bottomleft": gpts[2:4]}
    Path(out_json).write_text(json.dumps(overlay))
    return Image.open(out_webp).size, overlay


if __name__ == "__main__":
    size, ov = build(ROOT / "viewer" / "heppner.webp", ROOT / "viewer" / "heppner_overlay.json")
    print("heppner.webp", size)
    print("overlay:", json.dumps(ov))
