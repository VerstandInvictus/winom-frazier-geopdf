# Winom-Frazier OHV GeoPDF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decode, diagnose, and correct the georeferencing of three Winom-Frazier OHV trail-map PDFs, export a correct GeoTIFF, and ship a local no-login Leaflet viewer that overlays the map on a basemap with a simulated GPS marker.

**Architecture:** A small Python package (`geopdf/`) with focused modules — `pdfgeo` (pikepdf structural read), `crs` (pyproj CRS/area math), `report` (multi-file comparison), `diagnose` (validate vs known coords + decide fix path), `fix_surgical` (pikepdf in-place GPTS rewrite = Path A), `render` (pymupdf PDF→PNG), `raster` (rasterio GCP→GeoTIFF = Stage 4 + Path B) — wired through a thin `cli.py`. A static `viewer/` (Leaflet + geotiff.js + georaster-layer-for-leaflet) consumes the exported GeoTIFF.

**Tech Stack:** Python 3.12, pikepdf, pymupdf (fitz), pyproj, rasterio (GDAL bundled, Windows wheels), Leaflet + georaster-layer-for-leaflet (CDN). All Python deps install via `pip` — no conda/OSGeo4W.

**Key facts established during planning (real data from the PDFs):**
- GeoPDF structure is ISO-32000 geospatial: page `/VP` → viewport `/Measure` (`/Subtype /GEO`) → `/GPTS [lat lon …]` (geographic pairs, **lat first**), `/LPTS [0 1 0 0 1 0 1 1]`, `/GCS` → `/WKT (PROJCS["NAD_1983_Oregon_Washington_Albers", …])`.
- `Winom-Frazier OHV.pdf`: 1 active viewport, georeferenced to a ~0.5 km detail-inset box (`GPTS[45.1575 -118.642 45.1622 -118.642 45.1622 -118.637 45.1574 -118.637]`) — **wrong**.
- `Winom-Frazier OHV_260503_142151.pdf`: 2 active viewports + 7 embedded GPTS boxes total; the correct ~37×31 km trail extent is box `GPTS[44.8938 -118.766 45.2208 -118.759 45.2157 -118.362 44.8888 -118.372]`.
- `2025_WinomFrazierDesolationGuide.pdf`: no GPTS in plaintext — decode must decompress object streams to confirm whether it is georeferenced at all.
- Area is in **NE Oregon (Umatilla NF)**, not California — validate against user-supplied coordinates.

## REVISED APPROACH (after Task 1 decode revealed the true structure)

Decode of the real files overturned the original "wrong coordinates" theory. The actual situation:
- Both OHV PDFs have **7 named viewports** with **identical** georeferencing. `Winom-Frazier OHV.pdf` is the **2016 Adobe InDesign original**; `_260503` is a 2026 **PDFium re-save** (same georef, possibly degraded raster). The 2016 original is authoritative.
- The 7 viewports: `Where Are We` (regional locator), `State` (continental locator), `Map Frame` (page frame → multi-state), `Winom-FrazierData` (**the correct ~1132 km² / 37×31 km trail map**), and 3 tiny campground/trailhead detail insets (~0.2 km² each).
- **The georeferencing is correct.** The "snapped to a tiny box" symptom is a **multi-viewport precedence** problem: naive readers pick the wrong viewport (a campground inset) instead of `Winom-FrazierData`.
- `2025_WinomFrazierDesolationGuide.pdf` is a **separate 2-page guide, NOT georeferenced** (0 viewports); content ~2019.

**User decisions:** (1) Fix = **collapse to a single viewport** — keep only `Winom-FrazierData` from the 2016 original so every reader lands on the trail map. (2) **Render the 2025 guide** for visual comparison; georeference-from-scratch only if the user later judges it better.

This supersedes the original Task 4 ("rewrite GPTS"): coordinates are already correct, so the fix removes the confusing extra viewports instead. Task 3 reorients to *identify + validate* the main-map viewport and document the multi-viewport diagnosis. Task 5 additionally renders the 2025 guide pages. User's known coordinates become an independent confirmation (not required for the fix).

---

### Task 0: Project scaffold + dependency install

**Goal:** A runnable Python package skeleton with all geo dependencies importable.

**Files:**
- Create: `requirements.txt`
- Create: `geopdf/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `config/known_points.example.json`
- Create: `README.md`

**Acceptance Criteria:**
- [ ] `pip install -r requirements.txt` completes successfully
- [ ] `python -c "import pikepdf, fitz, pyproj, rasterio; print(pikepdf.__version__, fitz.__doc__[:5], pyproj.__version__, rasterio.__version__)"` prints versions with no ImportError
- [ ] `tests/conftest.py` exposes the three real PDF paths as a fixture
- [ ] `config/known_points.example.json` documents the coordinate input format

**Verify:** `python -c "import pikepdf, fitz, pyproj, rasterio; from rasterio.control import GroundControlPoint; print('ok')"` → prints `ok`

**Steps:**

- [ ] **Step 1: Create `requirements.txt`**

```text
pikepdf>=8,<10
pymupdf>=1.23
pyproj>=3.6
rasterio>=1.3
numpy>=1.24
Pillow>=10.0
pytest>=8.0
```

- [ ] **Step 2: Create package + test init files**

`geopdf/__init__.py`:
```python
"""Winom-Frazier OHV GeoPDF investigation and correction toolkit."""
__all__ = []
```

`tests/__init__.py`: (empty file)

- [ ] **Step 3: Create `tests/conftest.py` pointing at the real PDFs**

```python
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
```

- [ ] **Step 4: Create `config/known_points.example.json`**

```json
{
  "_comment": "Replace with 4-6 real features visible on the map, spread toward the N/S/E/W edges. lat/lon in decimal degrees (WGS84). Copy this file to config/known_points.json and fill in.",
  "points": [
    {"name": "Example Trailhead", "lat": 45.05, "lon": -118.56},
    {"name": "Example Campground", "lat": 45.18, "lon": -118.40}
  ]
}
```

- [ ] **Step 5: Create `README.md`**

```markdown
# Winom-Frazier OHV GeoPDF Toolkit

Decode, diagnose, and correct georeferencing for the Winom-Frazier OHV trail maps,
then view the result in a local browser map.

## Setup (Windows, system Python 3.12)
    python -m pip install -r requirements.txt

`rasterio` ships prebuilt Windows wheels with GDAL bundled — no conda/OSGeo4W needed.

## Usage
    python -m cli decode        # dump per-file georeferencing
    python -m cli report        # comparison table across all 3 PDFs -> docs/.../FINDINGS inputs
    python -m cli diagnose      # validate vs config/known_points.json, decide Path A/B
    python -m cli fix           # Path A: surgically correct the active viewport
    python -m cli export        # render corrected map -> viewer/winom-frazier_corrected.tif
    python -m http.server 8000  # then open http://localhost:8000/viewer/
```

- [ ] **Step 6: Install and verify**

Run: `python -m pip install -r requirements.txt`
Then run: `python -c "import pikepdf, fitz, pyproj, rasterio; from rasterio.control import GroundControlPoint; print('ok')"`
Expected: `ok`

> If `rasterio` fails to install on Windows: confirm 64-bit Python 3.12 (`python -c "import platform; print(platform.architecture())"`). PyPI ships `rasterio` cp312 win_amd64 wheels; upgrade pip first (`python -m pip install --upgrade pip`). conda-forge (`conda install -c conda-forge rasterio`) is the fallback only if wheels still fail.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt geopdf/ tests/ config/ README.md
git commit -m "chore: scaffold geopdf package and install geo deps"
```

---

### Task 1: Decode one PDF's georeferencing (`pdfgeo` + `crs`)

**Goal:** Given a PDF, extract every active viewport's geographic bounds plus a forensic scan of all embedded GPTS boxes, each with area/span/CRS.

**Files:**
- Create: `geopdf/crs.py`
- Create: `geopdf/pdfgeo.py`
- Test: `tests/test_pdfgeo.py`

**Acceptance Criteria:**
- [ ] `decode_pdf(path)` returns active viewports with lat/lon corner bounds, center, area_km2, span_km, and CRS name
- [ ] `scan_all_gpts(path)` finds all embedded GPTS boxes (incl. orphaned/inset ones), decompressing object streams when needed
- [ ] On `Winom-Frazier OHV.pdf`: the single active viewport decodes to the ~0.5 km inset box (area < 1 km²)
- [ ] On `Winom-Frazier OHV_260503_142151.pdf`: `scan_all_gpts` finds ≥7 boxes, including one with lat-span > 0.3° (the real trail extent)

**Verify:** `python -m pytest tests/test_pdfgeo.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write `geopdf/crs.py`**

```python
"""Coordinate-system parsing and geodesic measurements (pyproj)."""
from __future__ import annotations
import re
from dataclasses import dataclass
from pyproj import Geod, CRS

_GEOD = Geod(ellps="WGS84")


def crs_name_from_wkt(wkt: str | None) -> str:
    """Best-effort human name for a WKT string (handles ESRI-flavoured WKT)."""
    if not wkt:
        return "unknown"
    try:
        return CRS.from_user_input(wkt).name
    except Exception:
        m = re.search(r'(?:PROJCS|GEOGCS)\["([^"]+)"', wkt)
        return m.group(1) if m else "unparseable"


@dataclass
class Bounds:
    """Geographic bounds derived from 4 GPTS corner pairs (lat, lon)."""
    lats: list[float]
    lons: list[float]

    @property
    def lat_min(self) -> float: return min(self.lats)

    @property
    def lat_max(self) -> float: return max(self.lats)

    @property
    def lon_min(self) -> float: return min(self.lons)

    @property
    def lon_max(self) -> float: return max(self.lons)

    @property
    def center(self) -> tuple[float, float]:
        return ((self.lat_min + self.lat_max) / 2, (self.lon_min + self.lon_max) / 2)

    @property
    def area_km2(self) -> float:
        area, _ = _GEOD.polygon_area_perimeter(self.lons, self.lats)
        return abs(area) / 1e6

    @property
    def span_km(self) -> tuple[float, float]:
        """(width, height) in km across the bounding rectangle."""
        clat, _ = self.center
        _, _, w = _GEOD.inv(self.lon_min, clat, self.lon_max, clat)
        _, _, h = _GEOD.inv(self.lon_min, self.lat_min, self.lon_min, self.lat_max)
        return (w / 1000.0, h / 1000.0)


def bounds_from_gpts(gpts: list[float]) -> Bounds:
    """GPTS is a flat list of lat,lon pairs (ISO 32000: latitude first)."""
    lats = gpts[0::2]
    lons = gpts[1::2]
    return Bounds(lats=lats, lons=lons)
```

- [ ] **Step 2: Write `tests/test_pdfgeo.py` (failing first)**

```python
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
```

- [ ] **Step 3: Run tests to confirm they fail**

Run: `python -m pytest tests/test_pdfgeo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopdf.pdfgeo'`

- [ ] **Step 4: Write `geopdf/pdfgeo.py`**

```python
"""Structural read of geospatial PDFs via pikepdf."""
from __future__ import annotations
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
import pikepdf

from geopdf.crs import Bounds, bounds_from_gpts, crs_name_from_wkt


@dataclass
class Viewport:
    page_index: int
    bbox: list[float]
    bounds: Bounds
    crs_name: str
    wkt: str | None
    gpts: list[float]


@dataclass
class DecodeResult:
    path: str
    viewports: list[Viewport] = field(default_factory=list)


def _floats(arr) -> list[float]:
    return [float(x) for x in arr]


def _measure_to_viewport(page_index: int, bbox, measure) -> Viewport | None:
    gpts = measure.get("/GPTS")
    if gpts is None:
        return None
    gcs = measure.get("/GCS")
    wkt = None
    if gcs is not None and "/WKT" in gcs:
        wkt = str(gcs["/WKT"])
    gpts_f = _floats(gpts)
    return Viewport(
        page_index=page_index,
        bbox=_floats(bbox) if bbox is not None else [],
        bounds=bounds_from_gpts(gpts_f),
        crs_name=crs_name_from_wkt(wkt),
        wkt=wkt,
        gpts=gpts_f,
    )


def decode_pdf(path) -> DecodeResult:
    """Read the page-active /VP viewports (authoritative for GPS apps)."""
    result = DecodeResult(path=str(path))
    with pikepdf.open(str(path)) as pdf:
        for i, page in enumerate(pdf.pages):
            pageobj = getattr(page, "obj", page)
            vp = pageobj.get("/VP")
            if vp is None:
                continue
            for viewport in vp:
                measure = viewport.get("/Measure")
                if measure is None:
                    continue
                v = _measure_to_viewport(i, viewport.get("/BBox"), measure)
                if v is not None:
                    result.viewports.append(v)
    return result


_GPTS_RE = re.compile(rb"/GPTS\s*\[([^\]]+)\]")


def scan_all_gpts(path) -> list[Bounds]:
    """Forensic scan: every embedded GPTS box, including orphaned inset boxes.

    Reads raw bytes first; if no hits (streams compressed), saves a
    decompressed copy and rescans.
    """
    data = Path(path).read_bytes()
    matches = _GPTS_RE.findall(data)
    if not matches:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        with pikepdf.open(str(path)) as pdf:
            pdf.save(tmp_path, compress_streams=False,
                     object_stream_mode=pikepdf.ObjectStreamMode.disable)
        matches = _GPTS_RE.findall(Path(tmp_path).read_bytes())
    boxes: list[Bounds] = []
    for raw in matches:
        nums = [float(x) for x in raw.split()]
        if len(nums) >= 8:
            boxes.append(bounds_from_gpts(nums[:8]))
    return boxes
```

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_pdfgeo.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add geopdf/crs.py geopdf/pdfgeo.py tests/test_pdfgeo.py
git commit -m "feat: decode GeoPDF viewports and forensically scan GPTS boxes"
```

---

### Task 2: Multi-file comparison report (`report` + CLI)

**Goal:** Decode all three PDFs into one comparison table (JSON + Markdown) so the inset-vs-main story is visible at a glance.

**Files:**
- Create: `geopdf/report.py`
- Create: `cli.py`
- Test: `tests/test_report.py`

**Acceptance Criteria:**
- [ ] `build_report(paths)` returns a list of per-file records: filename, viewport count, each viewport's center/area/span/CRS, and total embedded GPTS-box count
- [ ] `render_markdown(report)` produces a table string
- [ ] `python -m cli report` writes `output/bounds_report.json` and prints the Markdown table
- [ ] Report flags any viewport with area_km2 < 1 as `SUSPECT (inset-scale)`

**Verify:** `python -m pytest tests/test_report.py -v` → all pass; then `python -m cli report` prints a 3-file table

**Steps:**

- [ ] **Step 1: Write `tests/test_report.py` (failing first)**

```python
from geopdf.report import build_report, render_markdown
from tests.conftest import PDFS


def test_report_flags_inset_scale():
    report = build_report(list(PDFS.values()))
    by_name = {r["filename"]: r for r in report}
    single = by_name["Winom-Frazier OHV.pdf"]
    assert single["viewport_count"] >= 1
    assert any(vp["flag"] == "SUSPECT (inset-scale)" for vp in single["viewports"])


def test_markdown_renders_all_files():
    report = build_report(list(PDFS.values()))
    md = render_markdown(report)
    assert "Winom-Frazier OHV.pdf" in md
    assert "2025_WinomFrazierDesolationGuide.pdf" in md
    assert "| File |" in md
```

- [ ] **Step 2: Run to confirm fail**

Run: `python -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopdf.report'`

- [ ] **Step 3: Write `geopdf/report.py`**

```python
"""Cross-file comparison report for the three trail-map PDFs."""
from __future__ import annotations
from pathlib import Path
from geopdf.pdfgeo import decode_pdf, scan_all_gpts


def _flag(area_km2: float) -> str:
    if area_km2 < 1:
        return "SUSPECT (inset-scale)"
    if area_km2 > 50_000:
        return "SUSPECT (region/state-scale)"
    return "plausible"


def build_report(paths) -> list[dict]:
    records = []
    for path in paths:
        path = Path(path)
        try:
            decoded = decode_pdf(path)
            all_boxes = scan_all_gpts(path)
        except Exception as exc:  # surface unreadable files instead of crashing
            records.append({"filename": path.name, "error": str(exc),
                            "viewport_count": 0, "viewports": [], "embedded_gpts_boxes": 0})
            continue
        vps = []
        for vp in decoded.viewports:
            w, h = vp.bounds.span_km
            vps.append({
                "center": [round(vp.bounds.center[0], 5), round(vp.bounds.center[1], 5)],
                "area_km2": round(vp.bounds.area_km2, 3),
                "span_km": [round(w, 2), round(h, 2)],
                "crs": vp.crs_name,
                "flag": _flag(vp.bounds.area_km2),
            })
        records.append({
            "filename": path.name,
            "viewport_count": len(decoded.viewports),
            "viewports": vps,
            "embedded_gpts_boxes": len(all_boxes),
        })
    return records


def render_markdown(report) -> str:
    lines = ["| File | Active VPs | Embedded boxes | Viewport center | Area km² | Span km | CRS | Flag |",
             "|---|---|---|---|---|---|---|---|"]
    for r in report:
        if r.get("error"):
            lines.append(f"| {r['filename']} | ERROR | - | - | - | - | - | {r['error']} |")
            continue
        if not r["viewports"]:
            lines.append(f"| {r['filename']} | 0 | {r['embedded_gpts_boxes']} | (none) | - | - | - | not georeferenced |")
        for vp in r["viewports"]:
            lines.append(
                f"| {r['filename']} | {r['viewport_count']} | {r['embedded_gpts_boxes']} | "
                f"{vp['center'][0]}, {vp['center'][1]} | {vp['area_km2']} | "
                f"{vp['span_km'][0]}×{vp['span_km'][1]} | {vp['crs']} | {vp['flag']} |")
    return "\n".join(lines)
```

- [ ] **Step 4: Write `cli.py` with the `report` and `decode` commands**

```python
"""Thin CLI dispatch for the geopdf toolkit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_PDFS = [
    PROJECT_ROOT / "2025_WinomFrazierDesolationGuide.pdf",
    PROJECT_ROOT / "Winom-Frazier OHV.pdf",
    PROJECT_ROOT / "Winom-Frazier OHV_260503_142151.pdf",
]
OUTPUT = PROJECT_ROOT / "output"


def cmd_decode(_args):
    from geopdf.pdfgeo import decode_pdf, scan_all_gpts
    for p in DEFAULT_PDFS:
        d = decode_pdf(p)
        print(f"\n=== {p.name} ===  active viewports: {len(d.viewports)}  "
              f"embedded boxes: {len(scan_all_gpts(p))}")
        for vp in d.viewports:
            print(f"  center={vp.bounds.center} area_km2={vp.bounds.area_km2:.3f} crs={vp.crs_name}")


def cmd_report(_args):
    from geopdf.report import build_report, render_markdown
    report = build_report(DEFAULT_PDFS)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "bounds_report.json").write_text(json.dumps(report, indent=2))
    print(render_markdown(report))
    print(f"\nWrote {OUTPUT / 'bounds_report.json'}")


def main():
    parser = argparse.ArgumentParser(prog="cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("decode").set_defaults(func=cmd_decode)
    sub.add_parser("report").set_defaults(func=cmd_report)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests + the command**

Run: `python -m pytest tests/test_report.py -v`
Expected: PASS (2 passed)
Run: `python -m cli report`
Expected: a Markdown table with all 3 files; `Winom-Frazier OHV.pdf` row flagged `SUSPECT (inset-scale)`

- [ ] **Step 6: Commit**

```bash
git add geopdf/report.py cli.py tests/test_report.py
git commit -m "feat: cross-file georeferencing comparison report + CLI"
```

---

### Task 3: Diagnose vs known coordinates + decide fix path (`diagnose` + CLI)

**Goal:** Validate each file's viewports against the user's known points, classify viewports, choose Path A vs Path B, and write FINDINGS.md.

**Files:**
- Create: `geopdf/diagnose.py`
- Modify: `cli.py` (add `diagnose` command)
- Test: `tests/test_diagnose.py`

**Acceptance Criteria:**
- [ ] `point_in_bounds(lat, lon, bounds)` correctly tests containment
- [ ] `classify_viewport(bounds, known_points)` returns one of: `main_map`, `inset`, `region`, `continental`, `off_region`
- [ ] `diagnose(paths, known_points)` returns, per file, which viewport (if any) is the correct trail extent and a recommended path (`A_surgical` if a correct box exists to copy from / only registration is wrong; `B_from_scratch` if the most-current map is not georeferenced)
- [ ] `write_findings(result, out_path)` writes a Markdown report citing concrete numbers
- [ ] Logic is covered by tests using synthetic coordinates (no dependency on the user's real values)

**Verify:** `python -m pytest tests/test_diagnose.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write `tests/test_diagnose.py` (failing first)**

```python
from geopdf.crs import Bounds
from geopdf.diagnose import point_in_bounds, classify_viewport


def _box(lat0, lon0, lat1, lon1):
    return Bounds(lats=[lat0, lat1, lat1, lat0], lons=[lon0, lon0, lon1, lon1])


def test_point_in_bounds():
    b = _box(45.0, -118.7, 45.2, -118.4)
    assert point_in_bounds(45.1, -118.5, b)
    assert not point_in_bounds(46.0, -118.5, b)


def test_classify_main_map_contains_points():
    b = _box(44.89, -118.77, 45.22, -118.36)   # real trail extent (~37x31 km)
    pts = [{"name": "th", "lat": 45.05, "lon": -118.56}]
    assert classify_viewport(b, pts) == "main_map"


def test_classify_inset_is_too_small():
    b = _box(45.157, -118.642, 45.162, -118.637)  # the ~0.5 km bug box
    pts = [{"name": "th", "lat": 45.05, "lon": -118.56}]
    assert classify_viewport(b, pts) == "inset"


def test_classify_continental():
    b = _box(12.8, -180.0, 58.0, -61.0)
    assert classify_viewport(b, []) == "continental"
```

- [ ] **Step 2: Run to confirm fail**

Run: `python -m pytest tests/test_diagnose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopdf.diagnose'`

- [ ] **Step 3: Write `geopdf/diagnose.py`**

```python
"""Validate georeferencing against known points and choose a fix path."""
from __future__ import annotations
import json
from pathlib import Path
from geopdf.crs import Bounds
from geopdf.pdfgeo import decode_pdf, scan_all_gpts


def point_in_bounds(lat: float, lon: float, b: Bounds) -> bool:
    return b.lat_min <= lat <= b.lat_max and b.lon_min <= lon <= b.lon_max


def classify_viewport(b: Bounds, known_points: list[dict]) -> str:
    lat_span = b.lat_max - b.lat_min
    lon_span = b.lon_max - b.lon_min
    if lat_span > 20 or lon_span > 20:
        return "continental"
    if lat_span > 2 or lon_span > 2:
        return "region"
    if b.area_km2 < 2:
        return "inset"
    if known_points:
        inside = sum(point_in_bounds(p["lat"], p["lon"], b) for p in known_points)
        if inside == 0:
            return "off_region"
    return "main_map"


def load_known_points(path) -> list[dict]:
    if not Path(path).exists():
        return []
    return json.loads(Path(path).read_text()).get("points", [])


def diagnose(paths, known_points: list[dict]) -> dict:
    files = []
    correct_box = None      # a Bounds known-good to copy from (Path A target)
    for path in paths:
        path = Path(path)
        decoded = decode_pdf(path)
        boxes = scan_all_gpts(path)
        active = [{"class": classify_viewport(vp.bounds, known_points),
                   "center": vp.bounds.center,
                   "area_km2": round(vp.bounds.area_km2, 3)} for vp in decoded.viewports]
        # any embedded box that looks like the real extent and contains the points
        main_candidates = [b for b in boxes
                           if classify_viewport(b, known_points) == "main_map"]
        if main_candidates and correct_box is None:
            correct_box = main_candidates[0]
        files.append({
            "filename": path.name,
            "active_viewports": active,
            "embedded_box_count": len(boxes),
            "has_correct_embedded_box": bool(main_candidates),
            "active_is_correct": any(a["class"] == "main_map" for a in active),
        })
    # Decision: if some file's active viewport is already correct -> nothing or trivial.
    # If a correct embedded box exists but active is wrong -> Path A (surgical).
    # If no correct box exists anywhere -> Path B (from scratch on newest map).
    any_correct_active = any(f["active_is_correct"] for f in files)
    any_correct_box = any(f["has_correct_embedded_box"] for f in files)
    if any_correct_active:
        path_decision = "ALREADY_CORRECT"
    elif any_correct_box:
        path_decision = "A_surgical"
    else:
        path_decision = "B_from_scratch"
    return {"files": files, "path_decision": path_decision,
            "correct_box": correct_box.__dict__ if correct_box else None,
            "known_point_count": len(known_points)}


def write_findings(result: dict, out_path) -> None:
    lines = ["# Winom-Frazier GeoPDF — Findings\n",
             f"**Decision:** `{result['path_decision']}`  ",
             f"**Known points used:** {result['known_point_count']}\n",
             "## Per-file\n"]
    for f in result["files"]:
        lines.append(f"### {f['filename']}")
        lines.append(f"- Active viewports: {len(f['active_viewports'])}; "
                     f"embedded GPTS boxes: {f['embedded_box_count']}")
        lines.append(f"- Active viewport correct: **{f['active_is_correct']}**; "
                     f"correct box embedded somewhere: **{f['has_correct_embedded_box']}**")
        for a in f["active_viewports"]:
            lines.append(f"  - {a['class']} @ {a['center']} ({a['area_km2']} km²)")
        lines.append("")
    Path(out_path).write_text("\n".join(lines))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_diagnose.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Add `diagnose` command to `cli.py`**

Add these to `cli.py` (new function + register in `main`):
```python
def cmd_diagnose(_args):
    from geopdf.diagnose import diagnose, load_known_points, write_findings
    points = load_known_points(PROJECT_ROOT / "config" / "known_points.json")
    if not points:
        print("WARNING: config/known_points.json not found or empty — "
              "classification will rely on size heuristics only.")
    result = diagnose(DEFAULT_PDFS, points)
    OUTPUT.mkdir(exist_ok=True)
    findings = PROJECT_ROOT / "docs" / "superpowers" / "specs" / "2026-06-03-winom-frazier-FINDINGS.md"
    write_findings(result, findings)
    print(f"Decision: {result['path_decision']}")
    print(f"Wrote {findings}")
```
Register in `main`: `sub.add_parser("diagnose").set_defaults(func=cmd_diagnose)`

- [ ] **Step 6: Commit**

```bash
git add geopdf/diagnose.py cli.py tests/test_diagnose.py
git commit -m "feat: diagnose viewports vs known points and decide fix path"
```

---

### Task 4: Collapse to single viewport (`fix_surgical` + CLI)

> **SUPERSEDES the original "surgical GPTS rewrite".** Decode proved the coordinates are already correct; the bug is multi-viewport precedence. The fix collapses the page `/VP` array to keep ONLY the `Winom-FrazierData` main-map viewport (from the 2016 Adobe original `Winom-Frazier OHV.pdf`), so every reader lands on the trail map. Function: `collapse_to_single_viewport(in_path, out_path, keep_name)`. The original-GPTS-rewrite text below is retained for history but not implemented.

**Goal:** Rewrite the wrong active viewport's `/GPTS` (and/or repoint `/Measure`) to the correct trail-extent bounds, write `*_corrected.pdf`, and prove the fix by re-decoding.

**Files:**
- Create: `geopdf/fix_surgical.py`
- Modify: `cli.py` (add `fix` command)
- Test: `tests/test_fix_surgical.py`

**Acceptance Criteria:**
- [ ] `set_viewport_gpts(in_path, out_path, page_index, vp_index, gpts)` writes a new PDF with the given GPTS on that viewport
- [ ] After fixing `Winom-Frazier OHV.pdf` with the correct extent GPTS, `decode_pdf(corrected)` reports the active viewport as `main_map`-scale (area between 500 and 5000 km²) instead of the inset box
- [ ] Original file is untouched (non-destructive)

**Verify:** `python -m pytest tests/test_fix_surgical.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write `tests/test_fix_surgical.py` (failing first)**

```python
from geopdf.fix_surgical import set_viewport_gpts
from geopdf.pdfgeo import decode_pdf

# The correct ~37x31 km trail extent (box #4 from the dual file)
CORRECT_GPTS = [44.8938, -118.766, 45.2208, -118.759,
                45.2157, -118.362, 44.8888, -118.372]


def test_surgical_fix_replaces_inset_with_real_extent(pdfs, tmp_path):
    out = tmp_path / "ohv_corrected.pdf"
    set_viewport_gpts(pdfs["ohv_single"], out, page_index=0, vp_index=0, gpts=CORRECT_GPTS)
    decoded = decode_pdf(out)
    area = decoded.viewports[0].bounds.area_km2
    assert 500 < area < 5000          # trail-scale, not the <1 km² inset
    # original untouched
    original_area = decode_pdf(pdfs["ohv_single"]).viewports[0].bounds.area_km2
    assert original_area < 1.0
```

- [ ] **Step 2: Run to confirm fail**

Run: `python -m pytest tests/test_fix_surgical.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopdf.fix_surgical'`

- [ ] **Step 3: Write `geopdf/fix_surgical.py`**

```python
"""Path A: surgically rewrite a viewport's GPTS in place (vector preserved)."""
from __future__ import annotations
from pathlib import Path
import pikepdf


def set_viewport_gpts(in_path, out_path, page_index: int, vp_index: int,
                      gpts: list[float]) -> None:
    """Replace /GPTS on the given page's /VP[vp_index] /Measure, write a new PDF.

    Non-destructive: reads in_path, writes out_path. gpts is a flat list of
    lat,lon pairs (4 corners, latitude first), matching LPTS [0 1 0 0 1 0 1 1].
    """
    if len(gpts) != 8:
        raise ValueError(f"expected 8 GPTS values (4 lat/lon pairs), got {len(gpts)}")
    with pikepdf.open(str(in_path)) as pdf:
        page = pdf.pages[page_index]
        pageobj = getattr(page, "obj", page)
        vp = pageobj.get("/VP")
        if vp is None:
            raise ValueError("page has no /VP viewport array")
        measure = vp[vp_index].get("/Measure")
        if measure is None:
            raise ValueError("viewport has no /Measure dictionary")
        measure["/GPTS"] = pikepdf.Array([float(x) for x in gpts])
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        pdf.save(str(out_path))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_fix_surgical.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Add `fix` command to `cli.py`**

Add to `cli.py`:
```python
# The correct ~37x31 km trail extent discovered during planning (box #4).
CORRECT_EXTENT_GPTS = [44.8938, -118.766, 45.2208, -118.759,
                       45.2157, -118.362, 44.8888, -118.372]


def cmd_fix(_args):
    from geopdf.fix_surgical import set_viewport_gpts
    from geopdf.pdfgeo import decode_pdf
    src = PROJECT_ROOT / "Winom-Frazier OHV.pdf"
    out = OUTPUT / "Winom-Frazier OHV_corrected.pdf"
    OUTPUT.mkdir(exist_ok=True)
    set_viewport_gpts(src, out, 0, 0, CORRECT_EXTENT_GPTS)
    vp = decode_pdf(out).viewports[0]
    print(f"Corrected -> {out}")
    print(f"  new center={vp.bounds.center} area_km2={vp.bounds.area_km2:.1f}")
```
Register in `main`: `sub.add_parser("fix").set_defaults(func=cmd_fix)`

> Note for execution: confirm the correct GPTS against the user's known points (and box #4) in Stage 3 before committing this as the canonical fix. If Stage 3 chose `B_from_scratch`, skip Path A and use Task 5's georeference path instead.

- [ ] **Step 6: Commit**

```bash
git add geopdf/fix_surgical.py cli.py tests/test_fix_surgical.py
git commit -m "feat: Path A surgical GPTS correction for the active viewport"
```

---

### Task 5: Render + georeference to GeoTIFF (`render` + `raster`, Stage 4 & Path B)

**Goal:** Rasterize the corrected map to a PNG and write an EPSG:4326 GeoTIFF, using a shared GCP→transform helper that also serves Path B (from-scratch georeferencing).

**Files:**
- Create: `geopdf/render.py`
- Create: `geopdf/raster.py`
- Modify: `cli.py` (add `export` command)
- Test: `tests/test_raster.py`

**Acceptance Criteria:**
- [ ] `render_page_png(pdf_path, page_index, dpi)` writes a PNG and returns (png_path, width_px, height_px)
- [ ] `corners_to_gcps(gpts, width, height)` maps the 4 GPTS corners to image pixels per LPTS `[0 1 0 0 1 0 1 1]`
- [ ] `write_geotiff(png_path, gcps, out_tif)` produces a valid EPSG:4326 GeoTIFF whose bounds match the GPTS corners (±0.001°)
- [ ] `python -m cli export` produces `viewer/winom-frazier_corrected.tif` readable by rasterio with the corrected bounds

**Verify:** `python -m pytest tests/test_raster.py -v` → all pass

**Steps:**

- [ ] **Step 1: Write `tests/test_raster.py` (failing first)**

```python
import numpy as np
import rasterio
from PIL import Image
from geopdf.raster import corners_to_gcps, write_geotiff

CORRECT_GPTS = [44.8938, -118.766, 45.2208, -118.759,
                45.2157, -118.362, 44.8888, -118.372]


def test_corners_map_to_image_pixels():
    gcps = corners_to_gcps(CORRECT_GPTS, width=1000, height=800)
    # LPTS[0 1 0 0 1 0 1 1]: first corner is top-left (col 0, row 0)
    assert (gcps[0].col, gcps[0].row) == (0, 0)
    assert gcps[0].y == 44.8938 and gcps[0].x == -118.766


def test_write_geotiff_bounds_match(tmp_path):
    png = tmp_path / "map.png"
    Image.fromarray(np.zeros((80, 100, 3), dtype=np.uint8)).save(png)
    gcps = corners_to_gcps(CORRECT_GPTS, width=100, height=80)
    out = tmp_path / "out.tif"
    write_geotiff(png, gcps, out)
    with rasterio.open(out) as ds:
        b = ds.bounds
        assert abs(b.left - (-118.766)) < 0.02
        assert abs(b.right - (-118.372)) < 0.02
        assert ds.crs.to_epsg() == 4326
```

- [ ] **Step 2: Run to confirm fail**

Run: `python -m pytest tests/test_raster.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'geopdf.raster'`
(If Pillow is missing, add `Pillow` to requirements.txt and `pip install Pillow`.)

- [ ] **Step 3: Write `geopdf/render.py`**

```python
"""Rasterize PDF pages to PNG via pymupdf (fitz)."""
from __future__ import annotations
from pathlib import Path
import fitz


def render_page_png(pdf_path, out_png, page_index: int = 0, dpi: int = 200):
    """Render a full page to PNG. Returns (out_png, width_px, height_px)."""
    doc = fitz.open(str(pdf_path))
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))
    doc.close()
    return Path(out_png), pix.width, pix.height
```

- [ ] **Step 4: Write `geopdf/raster.py`**

```python
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
    """Map 4 GPTS corners (lat,lon pairs) to image pixels.

    LPTS is fixed at [0 1 0 0 1 0 1 1] -> normalized (lx, ly) corners, ly up:
      (0,1)=top-left  (0,0)=bottom-left  (1,0)=bottom-right  (1,1)=top-right
    Pixel: col = lx*width, row = (1-ly)*height  (image y is down).
    """
    lpts = [(0.0, 1.0), (0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    gcps = []
    for i, (lx, ly) in enumerate(lpts):
        lat = gpts[i * 2]
        lon = gpts[i * 2 + 1]
        col = lx * width
        row = (1.0 - ly) * height
        gcps.append(GCP(row=row, col=col, x=lon, y=lat))
    return gcps


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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `python -m pytest tests/test_raster.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Add `export` command to `cli.py`**

Add to `cli.py`:
```python
VIEWER = PROJECT_ROOT / "viewer"


def cmd_export(_args):
    from geopdf.render import render_page_png
    from geopdf.raster import corners_to_gcps, write_geotiff
    corrected_pdf = OUTPUT / "Winom-Frazier OHV_corrected.pdf"
    src = corrected_pdf if corrected_pdf.exists() else (PROJECT_ROOT / "Winom-Frazier OHV.pdf")
    png, w, h = render_page_png(src, OUTPUT / "map.png", page_index=0, dpi=200)
    gcps = corners_to_gcps(CORRECT_EXTENT_GPTS, w, h)
    out = write_geotiff(png, gcps, VIEWER / "winom-frazier_corrected.tif")
    print(f"Wrote {out}  ({w}x{h}px)")
```
Register in `main`: `sub.add_parser("export").set_defaults(func=cmd_export)`

> Path B note for execution: when Stage 3 decides `B_from_scratch`, build `gcps` from the user's known points (pixel position located on the rendered newest-map PNG → real lat/lon) instead of `corners_to_gcps`, then call the same `write_geotiff`. The helper is path-agnostic.

- [ ] **Step 7: Commit**

```bash
git add geopdf/render.py geopdf/raster.py cli.py tests/test_raster.py
git commit -m "feat: render map to PNG and georeference to EPSG:4326 GeoTIFF"
```

---

### Task 6: Local no-login Leaflet GeoTIFF viewer

**Goal:** A static browser page that overlays the corrected GeoTIFF on an OpenStreetMap basemap, drops a simulated GPS marker from typed lat/lon, and optionally tracks live geolocation.

**Files:**
- Create: `viewer/index.html`
- Create: `viewer/app.js`
- Create: `viewer/style.css`
- Modify: `README.md` (add viewer run + manual verification steps)

**Acceptance Criteria:**
- [ ] `index.html` loads Leaflet + georaster + georaster-layer-for-leaflet from CDN
- [ ] `app.js` fetches `./winom-frazier_corrected.tif`, overlays it, and fits the map to its bounds
- [ ] A lat/lon form drops/moves a marker and pans to it
- [ ] A "track live GPS" toggle uses `navigator.geolocation.watchPosition`
- [ ] README documents `python -m http.server 8000` → `http://localhost:8000/viewer/`

**Verify:** Manual — run `python -m cli export` then `python -m http.server 8000`; open `http://localhost:8000/viewer/`; confirm the trail map overlays on the correct NE-Oregon location, and entering a known coordinate drops the dot in the right spot on the map.

**Steps:**

- [ ] **Step 1: Write `viewer/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Winom-Frazier OHV — GeoTIFF Viewer</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="./style.css" />
</head>
<body>
  <div id="panel">
    <h1>Winom-Frazier OHV</h1>
    <form id="gps-form">
      <label>Lat <input id="lat" type="number" step="any" placeholder="45.05" /></label>
      <label>Lon <input id="lon" type="number" step="any" placeholder="-118.56" /></label>
      <button type="submit">Drop GPS pin</button>
    </form>
    <label><input id="track" type="checkbox" /> Track live GPS</label>
    <label>Overlay opacity <input id="opacity" type="range" min="0" max="1" step="0.05" value="0.85" /></label>
    <p id="status">Loading GeoTIFF…</p>
  </div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/georaster@1.5.6/dist/georaster.browser.bundle.min.js"></script>
  <script src="https://unpkg.com/georaster-layer-for-leaflet@3.10.0/dist/georaster-layer-for-leaflet.min.js"></script>
  <script src="./app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Write `viewer/style.css`**

```css
html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
#map { position: absolute; inset: 0; z-index: 0; }
#panel {
  position: absolute; top: 10px; left: 10px; z-index: 1000;
  background: rgba(255,255,255,0.92); padding: 12px 14px; border-radius: 8px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.3); max-width: 240px;
}
#panel h1 { font-size: 15px; margin: 0 0 8px; }
#panel label { display: block; margin: 6px 0; font-size: 13px; }
#panel input[type="number"] { width: 90px; }
#status { font-size: 12px; color: #444; margin: 8px 0 0; }
```

- [ ] **Step 3: Write `viewer/app.js`**

```javascript
const map = L.map("map").setView([45.05, -118.56], 11);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19, attribution: "© OpenStreetMap",
}).addTo(map);

const status = document.getElementById("status");
let overlay = null;
let simMarker = null;
let liveMarker = null;
let watchId = null;

fetch("./winom-frazier_corrected.tif")
  .then((r) => {
    if (!r.ok) throw new Error("GeoTIFF not found — run `python -m cli export` first");
    return r.arrayBuffer();
  })
  .then((buf) => parseGeoraster(buf))
  .then((georaster) => {
    overlay = new GeoRasterLayer({ georaster, opacity: 0.85, resolution: 256 });
    overlay.addTo(map);
    map.fitBounds(overlay.getBounds());
    status.textContent = "GeoTIFF loaded.";
  })
  .catch((e) => { status.textContent = e.message; });

document.getElementById("opacity").addEventListener("input", (e) => {
  if (overlay) overlay.setOpacity(parseFloat(e.target.value));
});

document.getElementById("gps-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const lat = parseFloat(document.getElementById("lat").value);
  const lon = parseFloat(document.getElementById("lon").value);
  if (Number.isNaN(lat) || Number.isNaN(lon)) return;
  if (simMarker) simMarker.setLatLng([lat, lon]);
  else simMarker = L.marker([lat, lon]).addTo(map).bindPopup("Simulated GPS");
  simMarker.openPopup();
  map.panTo([lat, lon]);
});

document.getElementById("track").addEventListener("change", (e) => {
  if (e.target.checked) {
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        if (liveMarker) liveMarker.setLatLng([latitude, longitude]);
        else liveMarker = L.circleMarker([latitude, longitude], { color: "red" })
          .addTo(map).bindPopup("Live GPS");
        map.panTo([latitude, longitude]);
      },
      (err) => { status.textContent = "Geolocation: " + err.message; },
      { enableHighAccuracy: true },
    );
  } else if (watchId != null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }
});
```

- [ ] **Step 4: Update `README.md` viewer section**

Append to `README.md`:
```markdown
## Viewer
1. `python -m cli export`  (writes `viewer/winom-frazier_corrected.tif`)
2. `python -m http.server 8000`
3. Open `http://localhost:8000/viewer/`

The map overlays on OpenStreetMap. Type a lat/lon and "Drop GPS pin" to simulate a
location, or check "Track live GPS". Adjust overlay opacity to compare against the basemap.

**Manual verification:** the trail map should land on the Winom-Frazier area of the
Umatilla NF (≈45.05 N, −118.56 W). Enter a known trailhead/campground coordinate and
confirm the pin sits on that feature in the overlaid map.
```

- [ ] **Step 5: Manual smoke test**

Run: `python -m cli export`
Then run: `python -m http.server 8000`
Open `http://localhost:8000/viewer/` and confirm: overlay appears over NE Oregon, opacity slider works, dropping a pin at `45.05, -118.56` lands inside the map extent.

- [ ] **Step 6: Commit**

```bash
git add viewer/ README.md
git commit -m "feat: local no-login Leaflet GeoTIFF viewer with simulated GPS"
```

---

## Notes for execution

- **Run order:** Tasks are sequential (each builds on the prior). Stage 3 (`diagnose`) is the decision gate; it picks Path A (Task 4) or Path B (the Path-B branch inside Task 5). Build all tasks regardless — both paths are cheap and the viewer/export are shared.
- **User input needed at Stage 3:** copy `config/known_points.example.json` to `config/known_points.json` and fill in 4–6 real trailhead/campground coordinates before running `python -m cli diagnose`.
- **Canonical correct extent** found during planning: `GPTS[44.8938 -118.766 45.2208 -118.759 45.2157 -118.362 44.8888 -118.372]` (box #4). Re-confirm against the user's points before treating it as final.
- **North-up caveat:** `georaster-layer-for-leaflet` reads the GeoTIFF's transform corners and ignores rotation/shear. The Winom-Frazier map is near-north-up, so the EPSG:4326 affine from `write_geotiff` overlays correctly. If the overlay ever looks sheared (a rotated source map), warp to a clean north-up grid with `rasterio.warp.reproject(..., dst_crs="EPSG:4326")` before viewing.
