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
    """Map the 4 GPTS geographic corners to image pixel corners, north-up.

    The rendered map is visually north-up, but the PDF viewport's LPTS/BBox
    y-axis is inverted, so GPTS index order does NOT correspond to pixel-corner
    order. Instead, classify the four corners by latitude/longitude and place:
      NW -> top-left (0,0)      NE -> top-right (width,0)
      SW -> bottom-left (0,h)   SE -> bottom-right (width,h)
    Valid for north-up, near-axis-aligned maps (these USFS maps qualify).
    """
    pts = [(gpts[i * 2], gpts[i * 2 + 1]) for i in range(4)]  # (lat, lon)
    by_lat = sorted(pts, key=lambda p: p[0])
    south, north = by_lat[:2], by_lat[2:]
    nw = min(north, key=lambda p: p[1])
    ne = max(north, key=lambda p: p[1])
    sw = min(south, key=lambda p: p[1])
    se = max(south, key=lambda p: p[1])
    placement = [
        (nw, 0.0, 0.0),
        (ne, float(width), 0.0),
        (se, float(width), float(height)),
        (sw, 0.0, float(height)),
    ]
    return [GCP(row=row, col=col, x=lon, y=lat) for (lat, lon), col, row in placement]


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
