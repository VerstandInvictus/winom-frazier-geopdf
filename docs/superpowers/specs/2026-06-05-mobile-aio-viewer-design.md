# Mobile AIO Field Viewer — Design

**Date:** 2026-06-05
**Status:** Approved design (pre-implementation)
**Author:** Peter Cawley + Claude

## 1. Problem / Goal

A minimal, **offline**, installable field viewer for the Winom-Frazier OHV trail map, usable on **iOS and Android** in the backcountry with **no cell signal** and **no laptop/server running**. It must show the georeferenced trail map(s), track the user's **live GPS** position on them, and present a compact **mini-legend**. The current `viewer/` requires a local `python -m http.server` and multiple files — not field-portable.

## 2. Key decisions (from brainstorming)

- **Delivery = PWA on GitHub Pages (public repo).** A raw single-file `file://` HTML **cannot** get live GPS on iOS — since iOS 14.5, `navigator.geolocation` returns `PERMISSION_DENIED` in non-secure contexts, and `file://` is non-secure ([caniuse](https://caniuse.com/mdn-api_navigator_geolocation_secure_context_required)). The standard fix is a PWA served once over HTTPS, cached by a service worker, installed to the home screen, then run fully offline (an installed PWA is a secure context, so GPS works).
- **Reliability for "cache once, use months later":** require **Add to Home Screen** (installed PWAs are exempt from iOS's 7-day unused-site eviction) and call **`navigator.storage.persist()`** (prevents eviction under storage pressure). Residual risk is only user-driven (manual clear / delete app).
- **Hosting** = GitHub Pages from a **public** repo (the map is a public USFS sheet; nothing sensitive). Served from GitHub's CDN, independent of the user's machine.
- **Base maps = both, toggleable:** the re-pinned **2016 raster** (validated by the user's GPX, ~116 m RMS) and the **2025 vector SVG** (~126 m RMS).
- **v1 features:** both maps (toggle), live GPS dot, **recenter-on-me** button, **GPX route loading**, **minimizable mini-legend** in the controls pane.
- **Mini-legend = reimplemented compact HTML/CSS** (flowable, mobile-friendly), with symbology extracted faithfully from the sheets — not a sliced raster.
- **Rendering = reuse Leaflet** (`L.imageOverlay.rotated` for the raster, `L.svgOverlay` for the vector) rather than a custom canvas viewer; the both-maps requirement makes Leaflet the pragmatic choice.
- **Offline assets are vendored locally** (Leaflet 1.9.4 + Leaflet.ImageOverlay.Rotated copied into the app) — CDNs are unavailable offline.
- **Service worker = hand-rolled cache-first**, ~30 lines, no Workbox/bundler/build step.
- **2016 raster re-encoded to WebP** (~24 MB PNG → ~4 MB) to keep the offline cache small; no visible quality loss.

## 3. Architecture

A self-contained PWA in a new top-level **`app/`** directory (so GitHub Pages serves just that folder), independent of the Python toolkit in the repo. Five focused units:

### 3.1 PWA shell
- `app/index.html` — viewer markup + controls pane, with inlined CSS (keeps the file count minimal).
- `app/manifest.webmanifest` — `name`, `short_name`, `display: standalone`, `start_url`, `theme/background color`, icons (192/512 PNG).
- `app/sw.js` — cache-first service worker. On `install`: `cache.addAll([...fixed asset list...])` (html, app js/css, vendored leaflet js/css + plugin, both maps, overlay JSONs, icons). On `fetch`: serve from cache, fall back to network.
- First-run logic (in `app.js`): register SW, call `navigator.storage.persist()`, and show a dismissible **"Add to Home Screen"** hint.

### 3.2 Map core (`app/app.js`)
- Leaflet map, no basemap (the trail map is the map), default CRS.
- **2016**: `L.imageOverlay.rotated('map2016.webp', tl, tr, bl)` using `overlay2016.json` corners.
- **2025**: `L.svgOverlay(page2.svg, bounds)` using `page2_overlay.json`.
- **Base-map toggle** (segmented control: 2016 / 2025) swapping the active overlay; fit bounds on switch.

### 3.3 GPS module
- `navigator.geolocation.watchPosition` → a **blue dot** (`L.circleMarker`) + **accuracy ring** (`L.circle` of `coords.accuracy`).
- **Recenter-on-me** button: `map.setView(lastFix)`; disabled until first fix.
- Errors: permission denied / unavailable → non-blocking status message; map stays usable.

### 3.4 GPX loader
- File input → parse `trkpt`/`rtept`/`wpt` (port `parseGpxLatLngs` from `viewer/app.js`) → red polyline + start/end markers; fit bounds.

### 3.5 Mini-legend
- Collapsible panel inside the controls pane (minimize/expand toggle).
- **Reimplemented** symbology as HTML/CSS swatches: trail-difficulty colors, trail-type line styles (ATV / motorcycle / 4WD), and key point symbols (campground, trailhead, etc.), captured from the 2016 + 2025 legends. Reflows on narrow screens.

## 4. Data flow

```
First load (online):
  fetch app over HTTPS -> SW install precaches all assets -> storage.persist()
  -> user "Add to Home Screen"
Field use (offline):
  launch installed PWA -> SW serves all assets from cache
  -> Leaflet renders selected map -> watchPosition draws live blue dot
  -> (optional) load a .gpx from device storage
```

## 5. Error handling

- **GPS denied/unavailable** → status message; viewer remains usable as a static map.
- **Old device / no WebP** → negligible (modern iOS 14+/Android support WebP); if needed, keep a PNG fallback in cache.
- **Offline cache miss** → shouldn't occur (full precache); SW returns cached `index.html` for navigations.
- **Storage eviction** → mitigated by install + `persist()`; documented in setup instructions.

## 6. Testing

- **Lighthouse PWA audit**: installable + offline-capable pass.
- **Manual on a real phone**: load online → install → enable airplane mode → confirm map renders, 2016/2025 toggle works, live blue dot tracks, GPX loads, mini-legend collapses/expands.
- **Regression**: georeferencing already validated (user's GPX sits "nuts on" the re-pinned 2016 map).

## 7. Deployment

- Make the repo **public**.
- Build the `app/` assets (re-encode WebP, copy `overlay2016.json` / `page2.svg` / `page2_overlay.json`, vendor Leaflet + plugin, generate icons).
- Enable **GitHub Pages** serving `app/` (Pages-from-folder, or a minimal GitHub Action) → `https://verstandinvictus.github.io/winom-frazier-geopdf/`.
- Document the **one-time setup** (open URL → Add to Home Screen → allow location) in the app and README.

## 8. Inputs needed at build time

- Confirmation to make the repo public (and run the GitHub Pages enablement).
- The exact legend symbology — extracted from the 2016/2025 sheets during the mini-legend build.
- PWA app icons (can be generated from the map or a simple glyph).

## 9. Out of scope (v2)

Heading/compass + map-rotate, live coordinate readout, offline OSM base tiles, route recording/export, multi-map-area support.
