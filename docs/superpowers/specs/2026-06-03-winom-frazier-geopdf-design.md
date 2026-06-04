# Winom-Frazier OHV GeoPDF — Investigation, Correction & Viewer

**Date:** 2026-06-03
**Status:** Approved design (pre-implementation)
**Author:** Peter Cawley + Claude

## 1. Problem

Three PDF copies of a trail map for the **Winom-Frazier OHV complex** (Stanislaus National Forest, California) exist in this folder. At least one is a GeoPDF, and it is suspected to be georeferenced to the small "where are you on a state map" inset box rather than to the actual bounding box of the trail system.

We want to:

1. Determine which of the three PDFs are georeferenced and whether any is correct.
2. Identify which file is most up-to-date / most complete.
3. Produce one corrected, **open-standard** georeferenced map (vector GeoPDF + GeoTIFF) for the best content.
4. Build a local, **no-login, open** web viewer to verify and use the result on Windows — including dropping a simulated GPS location.

Explicitly NOT wanted: Avenza Maps or any login-walled / paid app. Output must open in anything (QGIS, generic GIS, browser).

## 2. Reconnaissance findings (already gathered)

Raw byte scan of the three files for geospatial dictionary markers:

| File | Size | Geo structure detected |
|---|---|---|
| `2025_WinomFrazierDesolationGuide.pdf` | 2.9 MB | No geospatial dict in plaintext — likely **not** a GeoPDF (or geo data is inside compressed object streams; needs deeper check). Only file explicitly dated 2025. |
| `Winom-Frazier OHV.pdf` | 3.8 MB | ISO-32000 geospatial PDF, **1 viewport** (`GPTS`, `Measure`, `WKT` present). |
| `Winom-Frazier OHV_260503_142151.pdf` | 3.8 MB | ISO-32000 geospatial PDF, **2 viewports** — consistent with the "main map + state inset" hypothesis. |

Both "OHV" files are genuine ISO-32000 geospatial PDFs. The `_260503` file's two viewports are exactly what the inset-box bug would look like: one viewport for the trail map, one for the inset — and a swap or mis-assignment of bounds is the suspected defect.

Machine tooling: Python 3.12 and gradio present. **No GDAL/rasterio yet** (will install). This folder is **not** a git repository.

## 3. Decisions (from brainstorming)

- **End goal:** a field-ready, corrected **GeoPDF** in an open standard; the web viewer is the verification harness (and a bonus general-purpose viewer).
- **Ground truth:** the **user will supply known real-world coordinates** of one or more features visible on the map. These are the authoritative validation. Cross-checking embedded bounds and visual sanity-check on a basemap are supporting checks.
- **Field app:** none of the walled apps. Open GeoPDF + GeoTIFF; browser-based viewing strongly desired.
- **Tooling:** install GDAL (prebuilt wheel or conda) for the full pipeline (GeoTIFF + raster overlay). pikepdf + pyproj for parsing/editing.
- **Recency vs. geo (pre-authorized):** if the newest/most-complete map (plausibly the 2025 guide) is *not* georeferenced while the georeferenced files are older, **georeference the newest from scratch**, lifting control points from the already-correct geoPDF and/or the user's known coordinates. The Stage-2 diagnosis is the decision gate.

## 4. Architecture — five isolated stages

Each stage is a separate, independently testable unit with a defined input/output.

### Stage 1 — Decode (`decode_geopdf.py`)
- **Does:** opens each PDF (pikepdf), walks the page `/VP` viewport array, extracts each viewport's `GPTS` (geo ground-control points), `LPTS`/`BBox` (page-space points), `Measure`/`GCS` coordinate system (`WKT`/`EPSG`). Converts projected coordinates to lat/lon via pyproj when needed.
- **Output:** a comparison table (stdout + JSON) of every viewport across all 3 files: corner lat/lon bounds, center, width/height, area km², CRS.
- **Depends on:** pikepdf, pyproj.
- **Proves:** which files are georeferenced; whether a viewport is the tiny/off-region inset (the bug).

### Stage 2 — Diagnose & decide (`diagnose.py` + written report)
- **Does:** validates each file's bounds against the user-supplied known coordinates and the expected Stanislaus-NF region; rasterizes low-res thumbnails of all three to compare map content/recency.
- **Output:** a written verdict (`docs/superpowers/specs/2026-06-03-winom-frazier-FINDINGS.md`) naming which files are georeferenced, which is correct, what is wrong, and which content is most current — plus the gate decision **Path A** or **Path B**.
- **Depends on:** Stage 1 output, user coordinates, a PDF rasterizer (pdf→image; via GDAL/pdfium or pymupdf).

### Stage 3 — Correct
- **Path A — surgical fix (`fix_geopdf.py`, pikepdf):** rewrite the wrong viewport's `GPTS`/CRS in place → `*_corrected.pdf`. Vector preserved, open standard. Re-run Stage 1 on the output to prove the new bounds are right.
- **Path B — from-scratch (`georeference.py`, GDAL):** rasterize the newer/better map; build a ground-control-point list (feature page/pixel position → real lat/lon, sourced from the correct geoPDF and/or user coords); `gdal_translate -gcp` then `gdalwarp` → georeferenced raster. Re-validate against user coords.
- **Output:** corrected georeferenced map (PDF and/or warped raster).

### Stage 4 — Export GeoTIFF (`export_geotiff.py`, GDAL)
- **Does:** renders the corrected map to a georeferenced **GeoTIFF** in a web-friendly CRS (EPSG:4326 or 3857).
- **Output:** `winom-frazier_corrected.tif` — the robust, universally-openable artifact and the viewer's data source.
- **Depends on:** GDAL; Stage 3 output.

### Stage 5 — Viewer (`viewer/index.html`, static)
- **Does:** Leaflet + `geotiff.js` + `georaster-layer-for-leaflet` overlay the GeoTIFF on an OSM basemap; a lat/lon text input drops a **simulated GPS marker**; optional live browser geolocation. No server account, no login, no upload — served locally via `python -m http.server`.
- **Output:** working local web map; doubles as a reusable open GeoTIFF viewer.
- **Depends on:** Stage 4 GeoTIFF; CDN JS libs (or vendored locally).

## 5. Data flow

```
3 PDFs ──▶ [1 Decode] ──▶ bounds table (JSON)
                              │
        user coords ─────────▶ [2 Diagnose] ──▶ FINDINGS.md + Path A|B
                                                   │
                          Path A ◀────────────────┴────────────▶ Path B
                    [3a pikepdf fix]                        [3b GDAL GCP warp]
                          │                                        │
                          └───────────▶ corrected map ◀───────────┘
                                              │
                                       [4 Export GeoTIFF] ──▶ *.tif
                                              │
                                       [5 Leaflet viewer] ──▶ map + GPS dot
```

## 6. Error handling

- **Compressed object streams:** if Stage 1 finds no geo dict in plaintext, decompress object streams via pikepdf before concluding "not georeferenced" (relevant for the 2025 guide).
- **Unknown/odd CRS:** if `WKT` is non-standard or missing, fall back to EPSG from any embedded code; surface the raw WKT in the report rather than guessing.
- **GDAL install failure on Windows:** document the wheel/conda fallback; Stages 1–3a do not depend on GDAL, so partial progress is always possible.
- **Bounds validation failure:** if a "corrected" file still doesn't match user coords within tolerance, stop and report rather than emit a wrong file.

## 7. Verification / testing

- **Stage 1:** re-decode a file and confirm corner bounds round-trip; manually confirm the suspected inset viewport reads as a tiny/state-scale box.
- **Stage 2:** the verdict must cite specific numbers (claimed bounds vs. user coords vs. expected region).
- **Stage 3:** the corrected file's decoded bounds must place the user's known coordinates at the correct on-map position within a stated tolerance.
- **Stage 5:** load the GeoTIFF; confirm the overlay lands on the correct mountains/trails on OSM, and a typed known coordinate drops the dot in the right spot on the map.

## 8. Deliverables

- `winom-frazier_corrected.pdf` (canonical vector GeoPDF, open standard)
- `winom-frazier_corrected.tif` (GeoTIFF)
- `docs/superpowers/specs/2026-06-03-winom-frazier-FINDINGS.md` (one-page report)
- `viewer/index.html` (local, no-login web viewer)
- The Stage 1–4 Python scripts, runnable and documented

## 9. Inputs required at execution time

- **User's known coordinates:** feature name(s) + lat/lon, for Stage 2 validation.
- **OK to install** `pikepdf`, `pyproj`, `gdal` into the user's Python 3.12 (GDAL via prebuilt wheel or conda).

## 10. Out of scope (for now)

- Phone-app packaging / offline basemap tiles / hosted public viewer.
- A polished click-to-pick GCP UI (Path B uses a scripted/manual control-point list).
- Editing the map's drawn content (we fix georeferencing, not cartography).

## 11. Open question to resolve during execution

- Whether the 2025 Desolation Guide is materially newer in content (new trails/closures) vs. just a restyle — decided in Stage 2, triggering Path A or Path B.
