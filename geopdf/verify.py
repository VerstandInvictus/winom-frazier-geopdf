"""Plot known ground-truth points on a georeferenced raster for accuracy checks.

We can't auto-detect where the map *draws* a feature, so this is a visual tool:
it places a crosshair at each real coordinate and emits a whole-map overview plus
a tight crop per point. You compare the crosshair to where the map shows the
feature; offset (in the printed m/px) is the registration error.
"""
from __future__ import annotations
import math
from pathlib import Path

import rasterio
from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower() or "point"


def verify_points(tif_path, points, out_dir, crop_px: int = 460) -> dict:
    """Locate each {name,lat,lon} on the raster, annotate, and crop.

    Writes <out_dir>/verify_overview.png and <out_dir>/verify_<name>.png (per
    in-bounds point). Returns a summary dict with per-point pixel + in_bounds,
    metres-per-pixel, crop width in metres, and raster size.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with rasterio.open(tif_path) as ds:
        inv = ~ds.transform
        W, H = ds.width, ds.height
        b = ds.bounds
        lat_mid = (b.top + b.bottom) / 2
        mpp = (b.right - b.left) * 111320.0 * math.cos(math.radians(lat_mid)) / W
        base = Image.open(tif_path).convert("RGB")

    overview = base.copy()
    od = ImageDraw.Draw(overview)
    ofont = _font(max(24, W // 60))
    big = max(30, W // 110)
    thick = max(3, W // 700)
    results = []
    for p in points:
        name, lat, lon = p["name"], float(p["lat"]), float(p["lon"])
        col, row = inv * (lon, lat)
        col, row = int(round(col)), int(round(row))
        in_bounds = 0 <= col < W and 0 <= row < H
        results.append({"name": name, "lat": lat, "lon": lon,
                        "pixel": [col, row], "in_bounds": in_bounds})
        if not in_bounds:
            continue
        od.ellipse([col - big, row - big, col + big, row + big], outline=(255, 0, 0), width=thick)
        od.line([col - big, row, col + big, row], fill=(255, 0, 0), width=thick)
        od.line([col, row - big, col, row + big], fill=(255, 0, 0), width=thick)
        od.text((col + big + 8, row - big), name, fill=(200, 0, 0), font=ofont)

        half = crop_px // 2
        crop = base.crop((col - half, row - half, col + half, row + half)).copy()
        cd = ImageDraw.Draw(crop)
        c = half
        cd.line([c - 40, c, c + 40, c], fill=(255, 0, 0), width=2)
        cd.line([c, c - 40, c, c + 40], fill=(255, 0, 0), width=2)
        cd.ellipse([c - 10, c - 10, c + 10, c + 10], outline=(255, 0, 0), width=2)
        crop = crop.resize((crop_px * 2, crop_px * 2), Image.NEAREST)
        crop.save(out_dir / f"verify_{_safe(name)}.png")

    overview.save(out_dir / "verify_overview.png")
    return {"results": results, "m_per_px": mpp, "crop_m": crop_px * mpp, "size": [W, H]}
