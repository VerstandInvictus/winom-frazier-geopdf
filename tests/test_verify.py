import math
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.crs import CRS
from PIL import Image

from geopdf.verify import verify_points


def _make_tif(path, west=-118.77, south=44.89, east=-118.36, north=45.22, w=400, h=400):
    transform = from_bounds(west, south, east, north, w, h)
    arr = np.full((3, h, w), 255, dtype="uint8")
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=3,
                       dtype="uint8", crs=CRS.from_epsg(4326), transform=transform) as ds:
        ds.write(arr)


def test_verify_locates_points_and_writes_outputs(tmp_path):
    tif = tmp_path / "t.tif"
    _make_tif(tif)
    out = tmp_path / "out"
    points = [
        {"name": "Center Point", "lat": 45.055, "lon": -118.565},  # ~middle -> in bounds
        {"name": "Far Away", "lat": 40.0, "lon": -100.0},          # off the raster
    ]
    summary = verify_points(tif, points, out)
    by_name = {r["name"]: r for r in summary["results"]}
    assert by_name["Center Point"]["in_bounds"] is True
    assert by_name["Far Away"]["in_bounds"] is False
    # in-bounds point lands near the raster centre
    col, row = by_name["Center Point"]["pixel"]
    assert 150 < col < 250 and 150 < row < 250
    assert summary["m_per_px"] > 0
    assert (out / "verify_overview.png").exists()
    assert (out / "verify_center_point.png").exists()       # crop written for in-bounds
    assert not (out / "verify_far_away.png").exists()       # none for out-of-bounds
