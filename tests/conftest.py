from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PDFS = {
    "guide_2025": PROJECT_ROOT / "2025_WinomFrazierDesolationGuide.pdf",
    "ohv_single": PROJECT_ROOT / "Winom-Frazier OHV.pdf",
    "ohv_dual": PROJECT_ROOT / "Winom-Frazier OHV_260503_142151.pdf",
}


@pytest.fixture
def pdfs():
    for name, path in PDFS.items():
        assert path.exists(), f"missing fixture PDF: {path}"
    return PDFS
