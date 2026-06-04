from geopdf.report import build_report, render_markdown
from tests.conftest import PDFS


def test_report_identifies_georeferencing_status():
    report = build_report(list(PDFS.values()))
    by_name = {r["filename"]: r for r in report}
    assert by_name["2025_WinomFrazierDesolationGuide.pdf"]["georeferenced"] is False
    assert by_name["Winom-Frazier OHV.pdf"]["georeferenced"] is True
    assert by_name["Winom-Frazier OHV.pdf"]["viewport_count"] == 7


def test_report_flags_main_map_and_insets():
    report = build_report(list(PDFS.values()))
    by_name = {r["filename"]: r for r in report}
    vps = by_name["Winom-Frazier OHV.pdf"]["viewports"]
    main = next(v for v in vps if v["name"] == "Winom-FrazierData")
    assert main["flag"] == "trail-scale"
    insets = [v for v in vps if "Cmpgrnd" in v["name"]]
    assert len(insets) == 3 and all(v["flag"] == "inset-scale" for v in insets)


def test_markdown_renders_all_files():
    report = build_report(list(PDFS.values()))
    md = render_markdown(report)
    assert "Winom-FrazierData" in md
    assert "2025_WinomFrazierDesolationGuide.pdf" in md
    assert "Georeferenced" in md
