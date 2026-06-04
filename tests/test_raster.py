import numpy as np
import rasterio
from PIL import Image
from geopdf.raster import corners_to_gcps, write_geotiff
from geopdf.render import render_page_png

# Winom-FrazierData main-map corners (lat,lon pairs), per LPTS [0 1 0 0 1 0 1 1]
MAIN_GPTS = [44.8938, -118.766, 45.2208, -118.759, 45.2157, -118.362, 44.8888, -118.372]


def test_corners_map_north_up():
    gcps = corners_to_gcps(MAIN_GPTS, width=1000, height=800)
    tl = next(g for g in gcps if g.col == 0 and g.row == 0)
    assert tl.y == 45.2208 and tl.x == -118.759     # NW corner at top-left
    bl = next(g for g in gcps if g.col == 0 and g.row == 800)
    assert bl.y == 44.8938 and bl.x == -118.766     # SW corner at bottom-left


def test_geotiff_is_north_up(tmp_path):
    import numpy as np
    import rasterio
    from PIL import Image
    png = tmp_path / "m.png"
    Image.fromarray(np.zeros((80, 100, 3), dtype=np.uint8)).save(png)
    gcps = corners_to_gcps(MAIN_GPTS, 100, 80)
    out = tmp_path / "o.tif"
    write_geotiff(png, gcps, out)
    with rasterio.open(out) as ds:
        top_y = (ds.transform * (0, 0))[1]              # latitude at top row
        bottom_y = (ds.transform * (0, ds.height))[1]   # latitude at bottom row
        assert top_y > bottom_y                          # north-up: top row is more northerly


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
