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
