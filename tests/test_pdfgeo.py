from geopdf.pdfgeo import decode_pdf, scan_all_gpts


def test_single_viewport_is_tiny_inset(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    assert len(result.viewports) >= 1
    vp = result.viewports[0]
    # Known truth: this file is wrongly referenced to a ~0.5 km detail inset
    assert vp.bounds.area_km2 < 1.0
    assert 45.15 < vp.bounds.center[0] < 45.17   # latitude
    assert -118.65 < vp.bounds.center[1] < -118.63  # longitude


def test_dual_file_scan_finds_real_extent(pdfs):
    boxes = scan_all_gpts(pdfs["ohv_dual"])
    assert len(boxes) >= 7
    spans = [b.lat_max - b.lat_min for b in boxes]
    assert max(spans) > 0.3   # the real ~37x31 km trail extent (box #4)


def test_crs_name_resolved(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    assert "Albers" in result.viewports[0].crs_name or result.viewports[0].crs_name != "unknown"
