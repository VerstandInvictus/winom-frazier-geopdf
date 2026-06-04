import numpy as np
import rasterio
from PIL import Image
from geopdf.raster import corners_to_gcps, write_geotiff
from geopdf.render import render_page_png

# Winom-FrazierData main-map corners (lat,lon pairs), per LPTS [0 1 0 0 1 0 1 1]
MAIN_GPTS = [44.8938, -118.766, 45.2208, -118.759, 45.2157, -118.362, 44.8888, -118.372]


def test_corners_map_to_image_pixels():
    gcps = corners_to_gcps(MAIN_GPTS, width=1000, height=800)
    assert (gcps[0].col, gcps[0].row) == (0, 0)            # first corner = top-left
    assert gcps[0].y == 44.8938 and gcps[0].x == -118.766


def test_write_geotiff_bounds_match(tmp_path):
    png = tmp_path / "map.png"
    Image.fromarray(np.zeros((80, 100, 3), dtype=np.uint8)).save(png)
    gcps = corners_to_gcps(MAIN_GPTS, width=100, height=80)
    out = tmp_path / "out.tif"
    write_geotiff(png, gcps, out)
    with rasterio.open(out) as ds:
        b = ds.bounds
        assert abs(b.left - (-118.766)) < 0.02
        assert abs(b.right - (-118.372)) < 0.02
        assert ds.crs.to_epsg() == 4326


def test_render_guide_page(pdfs, tmp_path):
    out, w, h = render_page_png(pdfs["guide_2025"], tmp_path / "g.png", page_index=0, dpi=100)
    assert out.exists() and w > 0 and h > 0
