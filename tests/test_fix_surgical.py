import pytest
from geopdf.fix_surgical import collapse_to_single_viewport
from geopdf.pdfgeo import decode_pdf


def test_collapse_keeps_only_main_map(pdfs, tmp_path):
    out = tmp_path / "collapsed.pdf"
    n = collapse_to_single_viewport(pdfs["ohv_single"], out, keep_name="Winom-FrazierData")
    assert n == 1
    decoded = decode_pdf(out)
    assert len(decoded.viewports) == 1
    vp = decoded.viewports[0]
    assert vp.name == "Winom-FrazierData"
    assert 800 < vp.bounds.area_km2 < 1500


def test_collapse_is_non_destructive(pdfs, tmp_path):
    out = tmp_path / "collapsed.pdf"
    collapse_to_single_viewport(pdfs["ohv_single"], out, keep_name="Winom-FrazierData")
    # original still has all 7 viewports
    assert len(decode_pdf(pdfs["ohv_single"]).viewports) == 7


def test_collapse_unknown_name_raises(pdfs, tmp_path):
    with pytest.raises(ValueError):
        collapse_to_single_viewport(pdfs["ohv_single"], tmp_path / "x.pdf", keep_name="Nope")
