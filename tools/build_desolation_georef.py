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

ROOT = Path(__file__).resolve().parents[1]
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


if __name__ == "__main__":
    size, ov = build(ROOT / "viewer" / "desolation.webp", ROOT / "viewer" / "desolation_overlay.json")
    print(f"desolation.webp {size}")
    print("overlay:", json.dumps(ov))
