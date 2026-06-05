"""Build a rotated raster overlay for heppner ohv.pdf page 1 (already geocoded).

Page 0 carries an embedded /VP viewport (NAD83 Oregon North State Plane GCS, GPTS in lat/lon).
Read the corners straight from the PDF -- but map them via LPTS normalization, because this
sheet's BBox is given with reversed y-order (y0 > y1), so a naive top/bottom assumption flips it.
The map prints north-up. Rendered + cropped to the bbox -> raster overlay like the others.

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
    x0, y0, x1, y1 = [float(v) for v in vp.BBox]
    lpts = [float(v) for v in vp.Measure.LPTS]
    gpts = [float(v) for v in vp.Measure.GPTS]
    pdf.close()

    # LPTS normalized corner -> geo [lat,lon]; normalize PDF points against the BBox as given
    lk = {(round(lpts[i]), round(lpts[i + 1])): [gpts[i], gpts[i + 1]] for i in range(0, 8, 2)}
    def geo(px, py):
        return lk[(round((px - x0) / (x1 - x0)), round((py - y0) / (y1 - y0)))]

    xl, xr = min(x0, x1), max(x0, x1)
    yb, yt = min(y0, y1), max(y0, y1)  # PDF y-up: yt = page-top of the region
    overlay = {"topleft": geo(xl, yt), "topright": geo(xr, yt), "bottomleft": geo(xl, yb)}

    fitz.open(str(SRC))[PAGE].get_pixmap(matrix=fitz.Matrix(SCALE, SCALE)).save(ROOT / "output" / "heppner_hi.png")
    img = Image.open(ROOT / "output" / "heppner_hi.png").convert("RGB")
    crop = (round(xl * SCALE), round((ph - yt) * SCALE), round(xr * SCALE), round((ph - yb) * SCALE))
    img.crop(crop).save(out_webp, "WEBP", quality=82, method=6)
    Path(out_json).write_text(json.dumps(overlay))
    return Image.open(out_webp).size, overlay


if __name__ == "__main__":
    size, ov = build(ROOT / "viewer" / "heppner.webp", ROOT / "viewer" / "heppner_overlay.json")
    print("heppner.webp", size)
    print("overlay:", json.dumps(ov))
