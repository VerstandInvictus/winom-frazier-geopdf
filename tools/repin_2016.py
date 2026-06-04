"""Re-pin the 2016 corrected map to config/transform_2016.json (the picker's better fit).

Rewrites viewer/winom-frazier_corrected.tif (used by the viewer) and writes
output/Winom-Frazier OHV_repinned.pdf (GPTS replaced, keeping LPTS corner order).
"""
import json
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import Affine
from rasterio.crs import CRS
from PIL import Image
import pikepdf

ROOT = Path(__file__).resolve().parents[1]
T = json.loads((ROOT / "config" / "transform_2016.json").read_text())
af = T["affine_px_to_lonlat"]
ex = json.loads((ROOT / "viewer" / "map2016_existing.json").read_text())["affine"]
newaff = lambda px, py: (af["a"] * px + af["b"] * py + af["c"], af["d"] * px + af["e"] * py + af["f"])
exaff = lambda px, py: (ex["a"] * px + ex["b"] * py + ex["c"], ex["d"] * px + ex["e"] * py + ex["f"])

img = np.asarray(Image.open(ROOT / "output" / "map.png").convert("RGB"))
H, Wd = img.shape[:2]
corners = [(0, 0), (Wd, 0), (Wd, H), (0, H)]

# ---- GeoTIFF re-pin (apply the affine directly) ----
tif = ROOT / "viewer" / "winom-frazier_corrected.tif"
transform = Affine(af["a"], af["b"], af["c"], af["d"], af["e"], af["f"])
with rasterio.open(tif, "w", driver="GTiff", height=H, width=Wd, count=3, dtype="uint8",
                   crs=CRS.from_epsg(4326), transform=transform, compress="lzw") as dst:
    for b in range(3):
        dst.write(img[:, :, b], b + 1)
print(f"re-pinned GeoTIFF -> {tif}")

# ---- GeoPDF re-pin (rewrite GPTS; keep each entry's LPTS corner slot via existing-georef match) ----
src = ROOT / "output" / "Winom-Frazier OHV_corrected.pdf"
out = ROOT / "output" / "Winom-Frazier OHV_repinned.pdf"
with pikepdf.open(str(src)) as pdf:
    pageobj = getattr(pdf.pages[0], "obj", pdf.pages[0])
    for v in pageobj["/VP"]:
        meas = v.get("/Measure")
        if meas is None or "/GPTS" not in meas:
            continue
        gpts = [float(x) for x in meas["/GPTS"]]
        new = []
        for k in range(len(gpts) // 2):
            lat, lon = gpts[2 * k], gpts[2 * k + 1]
            best = min(corners, key=lambda c: (exaff(*c)[0] - lon) ** 2 + (exaff(*c)[1] - lat) ** 2)
            nlon, nlat = newaff(*best)
            new += [nlat, nlon]
        meas["/GPTS"] = pikepdf.Array([float(x) for x in new])
    pdf.save(str(out))
print(f"re-pinned GeoPDF -> {out}")

import sys
sys.path.insert(0, str(ROOT))
from geopdf.pdfgeo import decode_pdf
for vp in decode_pdf(out).viewports:
    print(f"  {vp.name}: center={vp.bounds.center} area_km2={vp.bounds.area_km2:.0f}")
