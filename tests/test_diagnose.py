from geopdf.crs import Bounds
from geopdf.diagnose import point_in_bounds, classify_viewport, diagnose
from tests.conftest import PDFS


def _box(lat0, lon0, lat1, lon1):
    return Bounds(lats=[lat0, lat1, lat1, lat0], lons=[lon0, lon0, lon1, lon1])


def test_point_in_bounds():
    b = _box(45.0, -118.7, 45.2, -118.4)
    assert point_in_bounds(45.1, -118.5, b)
    assert not point_in_bounds(46.0, -118.5, b)


def test_classify_main_map_contains_points():
    b = _box(44.89, -118.77, 45.22, -118.36)
    pts = [{"name": "th", "lat": 45.05, "lon": -118.56}]
    assert classify_viewport(b, pts) == "main_map"


def test_classify_inset_is_too_small():
    b = _box(45.157, -118.642, 45.162, -118.637)
    assert classify_viewport(b, [{"name": "th", "lat": 45.05, "lon": -118.56}]) == "inset"


def test_classify_continental():
    b = _box(12.8, -180.0, 58.0, -61.0)
    assert classify_viewport(b, []) == "continental"


def test_diagnose_recommends_collapse_and_finds_main_map():
    result = diagnose(list(PDFS.values()), [])
    assert result["decision"] == "COLLAPSE_TO_SINGLE_VIEWPORT"
    ohv = next(f for f in result["files"] if f["filename"] == "Winom-Frazier OHV.pdf")
    assert ohv["main_map_name"] == "Winom-FrazierData"
    guide = next(f for f in result["files"] if f["filename"] == "2025_WinomFrazierDesolationGuide.pdf")
    assert guide["georeferenced"] is False
