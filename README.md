# Winom-Frazier OHV GeoPDF Toolkit

Decode, diagnose, and correct georeferencing for the Winom-Frazier OHV trail maps,
then view the result in a local browser map.

## Setup (Windows, system Python 3.12)
    python -m pip install -r requirements.txt

`rasterio` ships prebuilt Windows wheels with GDAL bundled — no conda/OSGeo4W needed.

## Usage
    python -m cli decode         # dump per-file georeferencing (all viewports)
    python -m cli report         # comparison table across all 3 PDFs -> output/bounds_report.{json,md}
    python -m cli diagnose       # identify the main-map viewport, validate, write FINDINGS.md
    python -m cli fix            # collapse to the single Winom-FrazierData viewport -> output/*_corrected.pdf
    python -m cli export         # render corrected main map -> viewer/winom-frazier_corrected.tif
    python -m cli render-guide   # rasterize the 2025 guide pages -> output/guide_page{1,2}.png
    python -m cli verify         # plot config/known_points.json on the GeoTIFF -> output/verify_*.png
    #   (verify --tif <other.tif> checks any GeoTIFF, e.g. a future from-scratch georeference)
    python -m http.server 8000   # then open http://localhost:8000/viewer/

`diagnose` reads optional known coordinates from `config/known_points.json`
(copy `config/known_points.example.json`) for independent validation; the fix
itself preserves the already-correct coordinates and does not require them.

## Viewer
1. `python -m cli export`  (writes `viewer/winom-frazier_corrected.tif`)
2. `python -m http.server 8000`
3. Open `http://localhost:8000/viewer/`

The map overlays on OpenStreetMap. Type a lat/lon and "Drop GPS pin" to simulate a
location, or check "Track live GPS". Adjust overlay opacity to compare against the basemap.

**Manual verification:** the trail map should land on the Winom-Frazier area of the
Umatilla NF (≈45.05 N, −118.56 W). Enter a known trailhead/campground coordinate and
confirm the pin sits on that feature in the overlaid map.

## Field viewer (offline PWA)

A self-contained installable web app in `app/` (deployed via GitHub Pages at the
custom domain **https://winom.app/**, set by `app/CNAME`). Open it on your phone, then:

1. **Add to Home Screen** (Share → Add to Home Screen) — required for offline use and GPS on iOS.
2. Launch it from the Home Screen icon and **allow Location**.
3. It caches both maps on first load; after that it works fully offline with live GPS.

Toggle the 2016 / 2025 maps, load a `.gpx` route, and tap "Recenter on me." The 2016
raster (re-encoded WebP) renders via a rotated image overlay; the 2025 vector via an
SVG overlay; a hand-rolled cache-first service worker + `navigator.storage.persist()`
keep it durably offline. Deploy is automated by `.github/workflows/pages.yml`
(Pages source = GitHub Actions, serving `app/`).
