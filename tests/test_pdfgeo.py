from geopdf.pdfgeo import decode_pdf, scan_all_gpts


def test_decode_returns_all_seven_viewports_in_order(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    assert len(result.viewports) == 7
    # document order is preserved (no reshuffling/reversal)
    assert result.viewports[0].name == "Where Are We"
    assert result.viewports[3].name == "Winom-FrazierData"


def test_main_map_viewport_has_correct_trail_extent(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    main = next(vp for vp in result.viewports if vp.name == "Winom-FrazierData")
    assert 800 < main.bounds.area_km2 < 1500          # ~1132 km^2
    assert 44.88 < main.bounds.lat_min < 44.90
    assert 45.21 < main.bounds.lat_max < 45.23


def test_three_tiny_campground_insets(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    insets = [vp for vp in result.viewports if "Cmpgrnd" in vp.name]
    assert len(insets) == 3
    assert all(vp.bounds.area_km2 < 1.0 for vp in insets)


def test_both_ohv_files_share_identical_georeferencing(pdfs):
    a = decode_pdf(pdfs["ohv_single"])
    b = decode_pdf(pdfs["ohv_dual"])
    assert [vp.gpts for vp in a.viewports] == [vp.gpts for vp in b.viewports]


def test_scan_all_gpts_finds_every_box(pdfs):
    boxes = scan_all_gpts(pdfs["ohv_dual"])
    assert len(boxes) >= 7
    assert max(b.lat_max - b.lat_min for b in boxes) > 0.3


def test_crs_name_is_oregon_albers(pdfs):
    result = decode_pdf(pdfs["ohv_single"])
    assert "Albers" in result.viewports[3].crs_name
