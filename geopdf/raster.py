"""Georeference a rendered map PNG into a GeoTIFF (rasterio = GDAL bundled)."""
from __future__ import annotations
from pathlib import Path
import numpy as np
import rasterio
from rasterio.control import GroundControlPoint as GCP
from rasterio.transform import from_gcps
from rasterio.crs import CRS
from PIL import Image


def corners_to_gcps(gpts: list[float], width: int, height: int) -> list[GCP]:
    """Map 4 GPTS corners (lat,lon pairs) to image pixels.

    LPTS is fixed at [0 1 0 0 1 0 1 1] -> normalized (lx, ly) corners, ly up:
      (0,1)=top-left  (0,0)=bottom-left  (1,0)=bottom-right  (1,1)=top-right
    Pixel: col = lx*width, row = (1-ly)*height  (image y is down).
    """
    lpts = [(0.0, 1.0), (0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    gcps = []
    for i, (lx, ly) in enumerate(lpts):
        lat = gpts[i * 2]
        lon = gpts[i * 2 + 1]
        col = lx * width
        row = (1.0 - ly) * height
        gcps.append(GCP(row=row, col=col, x=lon, y=lat))
    return gcps


def write_geotiff(png_path, gcps: list[GCP], out_tif) -> Path:
    """Write an EPSG:4326 GeoTIFF from a PNG + 4 corner GCPs (affine fit)."""
    img = np.asarray(Image.open(png_path).convert("RGB"))
    height, width = img.shape[:2]
    transform = from_gcps(gcps)
    Path(out_tif).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        out_tif, "w", driver="GTiff", height=height, width=width,
        count=3, dtype="uint8", crs=CRS.from_epsg(4326), transform=transform,
    ) as dst:
        for b in range(3):
            dst.write(img[:, :, b], b + 1)
    return Path(out_tif)
