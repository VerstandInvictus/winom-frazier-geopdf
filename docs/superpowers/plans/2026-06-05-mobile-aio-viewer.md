# Mobile AIO Field Viewer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-extended-cc:subagent-driven-development (recommended) or superpowers-extended-cc:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A self-contained, installable offline PWA (`app/`) that shows the georeferenced Winom-Frazier trail maps with live GPS, served from GitHub Pages.

**Architecture:** Static PWA in a new top-level `app/` directory. Reuses the proven Leaflet rendering from `viewer/` (rotated image overlay for the 2016 raster, SVG overlay for the 2025 vector). All libraries vendored locally; a hand-rolled cache-first service worker precaches a fixed asset list; `navigator.storage.persist()` + Add-to-Home-Screen make it durably offline with working GPS on iOS/Android.

**Tech Stack:** HTML/CSS/JS, Leaflet 1.9.4 + Leaflet.ImageOverlay.Rotated (vendored), service worker + web manifest, Python/Pillow (WebP re-encode + icon generation), GitHub Pages.

**Asset reuse (already in repo, on this branch):** `viewer/map2016.png` (3873×4523, re-encode to WebP), `viewer/overlay2016.json` (2016 corners), `viewer/page2.svg` + `viewer/page2_overlay.json` (2025), `parseGpxLatLngs` in `viewer/app.js`. Legend reference crops in `output/_leg_*.png`.

**Serving locally for tests:** `python -m http.server 8001 -d app` then open `http://localhost:8001/`.

---

### Task 1: PWA shell (manifest + cache-first service worker + install/persist)

**Goal:** An installable, offline-capable shell that precaches its core files and persists storage.

**Files:**
- Create: `app/index.html`
- Create: `app/app.js`
- Create: `app/sw.js`
- Create: `app/manifest.webmanifest`
- Create: `app/icons/icon-192.png`, `app/icons/icon-512.png`

**Acceptance Criteria:**
- [ ] `app/index.html` loads with a controls panel and an (empty) `#map` area; no console errors
- [ ] `sw.js` registers, and on `install` precaches the core asset list; on `fetch` serves cache-first
- [ ] First run calls `navigator.storage.persist()` and shows a dismissible "Add to Home Screen" hint
- [ ] In DevTools "Offline", reloading still loads the shell from cache
- [ ] Lighthouse PWA category: "Installable" passes

**Verify:** `python -m http.server 8001 -d app`; open `http://localhost:8001/`; DevTools → Application → Service Workers shows activated; toggle Offline + reload → shell loads; Lighthouse → Installable.

**Steps:**

- [ ] **Step 1: Create `app/manifest.webmanifest`**

```json
{
  "name": "Winom-Frazier OHV Field Map",
  "short_name": "WF Trail Map",
  "start_url": ".",
  "scope": ".",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#2e6b2e",
  "icons": [
    { "src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

- [ ] **Step 2: Generate icons** (Pillow; simple brand glyph)

Run:
```bash
python -c "from PIL import Image, ImageDraw, ImageFont
for s in (192,512):
    im=Image.new('RGB',(s,s),'#2e6b2e'); d=ImageDraw.Draw(im)
    try: f=ImageFont.truetype('arialbd.ttf', int(s*0.42))
    except Exception: f=ImageFont.load_default()
    t='WF'; b=d.textbbox((0,0),t,font=f); d.text(((s-(b[2]-b[0]))/2,(s-(b[3]-b[1]))/2-b[1]),t,fill='white',font=f)
    import os; os.makedirs('app/icons',exist_ok=True); im.save(f'app/icons/icon-{s}.png')
print('icons written')"
```
Expected: `icons written`

- [ ] **Step 3: Create `app/sw.js`** (cache-first; core list only — expanded in Task 2)

```javascript
// Bump CACHE_VERSION whenever the ASSETS list changes (forces clients to re-cache).
const CACHE_VERSION = "wf-v1";
const ASSETS = [
  "./",
  "./index.html",
  "./app.js",
  "./manifest.webmanifest",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE_VERSION).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE_VERSION).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match("./index.html")))
  );
});
```

- [ ] **Step 4: Create `app/app.js`** (PWA bootstrap only — map/GPS/etc. added in later tasks)

```javascript
// ---- PWA bootstrap: service worker, persistent storage, install hint ----
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch((e) => console.warn("SW register failed", e));
}
if (navigator.storage && navigator.storage.persist) {
  navigator.storage.persist().then((granted) => console.log("persistent storage:", granted));
}
// One-time "Add to Home Screen" hint (hidden once dismissed or if already installed).
(function installHint() {
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  if (standalone || localStorage.getItem("wf-hint-dismissed")) return;
  const el = document.getElementById("install-hint");
  if (!el) return;
  el.hidden = false;
  el.querySelector("button").addEventListener("click", () => {
    el.hidden = true;
    localStorage.setItem("wf-hint-dismissed", "1");
  });
})();
```

- [ ] **Step 5: Create `app/index.html`** (shell + controls + inline CSS; Leaflet added in Task 2)

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#2e6b2e" />
  <title>Winom-Frazier OHV Field Map</title>
  <link rel="manifest" href="manifest.webmanifest" />
  <link rel="apple-touch-icon" href="icons/icon-192.png" />
  <style>
    html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
    #map { position: absolute; inset: 0; background: #e9e9e9; z-index: 0; }
    #panel { position: absolute; top: 8px; left: 8px; z-index: 1000; background: rgba(255,255,255,0.94);
      padding: 8px 10px; border-radius: 8px; box-shadow: 0 1px 6px rgba(0,0,0,0.3); max-width: 70vw; font-size: 14px; }
    #panel .row { margin: 4px 0; }
    #install-hint { position: absolute; bottom: 12px; left: 8px; right: 8px; z-index: 1001;
      background: #2e6b2e; color: #fff; padding: 10px; border-radius: 8px; font-size: 14px; }
    #install-hint button { margin-left: 8px; }
    button { font-size: 14px; padding: 4px 8px; }
  </style>
</head>
<body>
  <div id="panel">
    <div class="row"><strong>Winom-Frazier OHV</strong></div>
    <div class="row" id="status">Loading…</div>
  </div>
  <div id="install-hint" hidden>
    For offline GPS, add this to your Home Screen (Share → Add to Home Screen), then open it from there.
    <button type="button">Got it</button>
  </div>
  <div id="map"></div>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 6: Verify + commit**

Run: `python -m http.server 8001 -d app` and open `http://localhost:8001/`. Confirm: panel shows, no console errors, SW activates (Application tab), Offline reload still loads, Lighthouse "Installable" passes. Stop the server.
```bash
git add app/
git commit -m "feat(app): PWA shell — manifest, cache-first SW, persist + install hint"
```

---

### Task 2: Map core — both maps + toggle (vendored Leaflet)

**Goal:** Render the 2016 raster + 2025 vector with a toggle, all libs/assets vendored for offline.

**Files:**
- Create: `app/vendor/leaflet.js`, `app/vendor/leaflet.css`, `app/vendor/Leaflet.ImageOverlay.Rotated.js`
- Create: `app/map2016.webp`, `app/overlay2016.json`, `app/page2.svg`, `app/page2_overlay.json`
- Modify: `app/index.html` (add vendored Leaflet tags + base-map toggle markup)
- Modify: `app/app.js` (map init, overlays, toggle)
- Modify: `app/sw.js` (expand ASSETS, bump CACHE_VERSION)

**Acceptance Criteria:**
- [ ] 2016 WebP renders via `L.imageOverlay.rotated` using `overlay2016.json` corners (crisp, fast)
- [ ] 2025 SVG renders via `L.svgOverlay` using `page2_overlay.json` bounds
- [ ] A 2016/2025 toggle swaps the active overlay and fits its bounds
- [ ] Everything loads with **no network** (DevTools Offline) — all assets vendored & precached
- [ ] `python tools/check_app_assets.py` passes (every SW-listed asset exists)

**Verify:** Serve `app/`, DevTools Offline, reload → both maps render and toggle works; run the asset check.

**Steps:**

- [ ] **Step 1: Vendor Leaflet + plugin + copy data assets**

Run (PowerShell):
```powershell
New-Item -ItemType Directory -Force app/vendor | Out-Null
Invoke-WebRequest https://unpkg.com/leaflet@1.9.4/dist/leaflet.js -OutFile app/vendor/leaflet.js
Invoke-WebRequest https://unpkg.com/leaflet@1.9.4/dist/leaflet.css -OutFile app/vendor/leaflet.css
Invoke-WebRequest https://unpkg.com/leaflet-imageoverlay-rotated@0.2.1/Leaflet.ImageOverlay.Rotated.js -OutFile app/vendor/Leaflet.ImageOverlay.Rotated.js
Copy-Item viewer/overlay2016.json app/overlay2016.json
Copy-Item viewer/page2.svg app/page2.svg
Copy-Item viewer/page2_overlay.json app/page2_overlay.json
python -c "from PIL import Image; Image.open('viewer/map2016.png').convert('RGB').save('app/map2016.webp','WEBP',quality=82,method=6)"
$mb=[math]::Round((Get-Item app/map2016.webp).Length/1MB,1); Write-Output "map2016.webp = $mb MB"
```
Expected: `map2016.webp = ~3-5 MB`. Then edit `app/overlay2016.json` `"image"` field to `"map2016.webp"`.

- [ ] **Step 2: Add Leaflet tags + toggle to `app/index.html`**

In `<head>`, after the manifest link, add:
```html
  <link rel="stylesheet" href="vendor/leaflet.css" />
```
In `#panel`, after the status row, add:
```html
    <div class="row">
      Map: <button id="m2016" type="button">2016</button>
      <button id="m2025" type="button">2025</button>
    </div>
```
Before `<script src="app.js"></script>`, add:
```html
  <script src="vendor/leaflet.js"></script>
  <script src="vendor/Leaflet.ImageOverlay.Rotated.js"></script>
```

- [ ] **Step 3: Add map core to `app/app.js`** (append after the bootstrap block)

```javascript
// ---- Map core: 2016 raster (rotated overlay) + 2025 vector (SVG), toggle ----
const map = L.map("map", { zoomControl: true });
const status = document.getElementById("status");
let layer2016 = null, layer2025 = null, active = null, bounds2016 = null, bounds2025 = null;

function show(which) {
  if (which === active) return;
  if (layer2016 && map.hasLayer(layer2016)) map.removeLayer(layer2016);
  if (layer2025 && map.hasLayer(layer2025)) map.removeLayer(layer2025);
  if (which === "2016" && layer2016) { layer2016.addTo(map); map.fitBounds(bounds2016); }
  if (which === "2025" && layer2025) { layer2025.addTo(map); map.fitBounds(bounds2025); }
  active = which;
}

Promise.all([
  fetch("overlay2016.json").then((r) => r.json()),
  fetch("page2_overlay.json").then((r) => r.json()),
  fetch("page2.svg").then((r) => r.text()),
]).then(([o16, o25, svgText]) => {
  const tl = L.latLng(o16.topleft), tr = L.latLng(o16.topright), bl = L.latLng(o16.bottomleft);
  const br = L.latLng(tr.lat + bl.lat - tl.lat, tr.lng + bl.lng - tl.lng);
  layer2016 = L.imageOverlay.rotated("map2016.webp", tl, tr, bl, { opacity: 1, interactive: false });
  bounds2016 = L.latLngBounds([tl, tr, bl, br]);
  const svgEl = new DOMParser().parseFromString(svgText, "image/svg+xml").documentElement;
  layer2025 = L.svgOverlay(svgEl, o25.bounds, { opacity: 1, interactive: false });
  bounds2025 = L.latLngBounds(o25.bounds);
  show("2016");
  status.textContent = "Map loaded.";
}).catch((e) => { status.textContent = "Map load error: " + e.message; });

document.getElementById("m2016").addEventListener("click", () => show("2016"));
document.getElementById("m2025").addEventListener("click", () => show("2025"));
```

- [ ] **Step 4: Expand `app/sw.js` ASSETS + bump version**

Change `CACHE_VERSION` to `"wf-v2"` and replace `ASSETS` with:
```javascript
const ASSETS = [
  "./", "./index.html", "./app.js", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./vendor/leaflet.js", "./vendor/leaflet.css", "./vendor/Leaflet.ImageOverlay.Rotated.js",
  "./map2016.webp", "./overlay2016.json", "./page2.svg", "./page2_overlay.json",
];
```

- [ ] **Step 5: Create `tools/check_app_assets.py`** (asset-integrity test)

```python
"""Verify every asset listed in app/sw.js exists on disk (prevents offline cache misses)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sw = (ROOT / "app" / "sw.js").read_text()
listed = re.findall(r'"\./([^"]+)"', sw)
missing = [a for a in listed if a and not (ROOT / "app" / a).exists()]
if missing:
    print("MISSING assets referenced by sw.js:", missing)
    sys.exit(1)
print(f"OK: all {len(listed)} sw.js assets present")
```

- [ ] **Step 6: Verify + commit**

Run: `python tools/check_app_assets.py` → `OK: all N sw.js assets present`.
Serve `app/`, DevTools → Offline → reload → both maps render, 2016/2025 toggle works.
```bash
git add app/ tools/check_app_assets.py
git commit -m "feat(app): vendored Leaflet + 2016/2025 maps with toggle, offline-precached"
```

> Note: `app/map2016.webp` and `app/vendor/` are real committed assets (the PWA must be self-contained for GitHub Pages) — do NOT gitignore them.

---

### Task 3: GPS module — live dot + accuracy ring + recenter

**Goal:** Track the user's live position with a blue dot + accuracy ring and a recenter button.

**Files:**
- Modify: `app/index.html` (recenter button)
- Modify: `app/app.js` (geolocation watch + recenter)

**Acceptance Criteria:**
- [ ] `watchPosition` draws a blue dot (`L.circleMarker`) + accuracy ring (`L.circle`) that update on each fix
- [ ] "Recenter" button centers the map on the last fix; it is disabled until the first fix
- [ ] Permission denied / unavailable shows a non-blocking status message; the map stays usable

**Verify:** On a phone via the deployed PWA (Task 6), the blue dot tracks and recenter works. Locally, DevTools → Sensors → set a location and confirm the dot appears.

**Steps:**

- [ ] **Step 1: Add recenter button to `app/index.html`** (in `#panel`, after the map toggle row)

```html
    <div class="row"><button id="recenter" type="button" disabled>Recenter on me</button></div>
```

- [ ] **Step 2: Append GPS module to `app/app.js`**

```javascript
// ---- Live GPS: blue dot + accuracy ring + recenter ----
let gpsDot = null, gpsRing = null, lastFix = null;
const recenterBtn = document.getElementById("recenter");

if ("geolocation" in navigator) {
  navigator.geolocation.watchPosition(
    (pos) => {
      const { latitude, longitude, accuracy } = pos.coords;
      lastFix = [latitude, longitude];
      if (gpsDot) gpsDot.setLatLng(lastFix);
      else gpsDot = L.circleMarker(lastFix, { radius: 7, color: "#1565c0", fillColor: "#1565c0", fillOpacity: 0.9, weight: 2 }).addTo(map);
      if (gpsRing) { gpsRing.setLatLng(lastFix); gpsRing.setRadius(accuracy); }
      else gpsRing = L.circle(lastFix, { radius: accuracy, color: "#1565c0", weight: 1, fillOpacity: 0.08 }).addTo(map);
      recenterBtn.disabled = false;
    },
    (err) => { status.textContent = "GPS: " + err.message; },
    { enableHighAccuracy: true, maximumAge: 5000, timeout: 20000 }
  );
} else {
  status.textContent = "GPS not available on this device/context.";
}

recenterBtn.addEventListener("click", () => { if (lastFix) map.setView(lastFix, Math.max(map.getZoom(), 14)); });
```

- [ ] **Step 3: Verify + commit**

Locally: DevTools → Sensors → Location → custom (e.g. 45.05, -118.56) → reload → blue dot + ring appear; Recenter enables and centers.
```bash
git add app/
git commit -m "feat(app): live GPS dot + accuracy ring + recenter button"
```

---

### Task 4: GPX route loader

**Goal:** Load a `.gpx` from device storage and draw it as a route polyline.

**Files:**
- Modify: `app/index.html` (file input)
- Modify: `app/app.js` (port `parseGpxLatLngs`, draw track)

**Acceptance Criteria:**
- [ ] Selecting a `.gpx` draws a red polyline with green start / red end markers and fits bounds
- [ ] A GPX with no track points shows a clear "no coordinates" message
- [ ] Works offline (pure client-side parse)

**Verify:** Load the drive-in GPX; confirm the track draws on the active map.

**Steps:**

- [ ] **Step 1: Add file input to `app/index.html`** (in `#panel`)

```html
    <div class="row">GPX <input id="gpx" type="file" accept=".gpx,application/gpx+xml" /></div>
```

- [ ] **Step 2: Append GPX loader to `app/app.js`** (ported from `viewer/app.js`)

```javascript
// ---- GPX track loader ----
let gpxLayer = null;
function parseGpxLatLngs(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("invalid GPX/XML");
  let pts = [...doc.querySelectorAll("trkpt")];
  if (!pts.length) pts = [...doc.querySelectorAll("rtept")];
  if (!pts.length) pts = [...doc.querySelectorAll("wpt")];
  return pts.map((p) => [parseFloat(p.getAttribute("lat")), parseFloat(p.getAttribute("lon"))])
    .filter(([la, lo]) => !Number.isNaN(la) && !Number.isNaN(lo));
}
document.getElementById("gpx").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const ll = parseGpxLatLngs(reader.result);
      if (!ll.length) { status.textContent = "GPX has no coordinates."; return; }
      if (gpxLayer) gpxLayer.remove();
      gpxLayer = L.layerGroup([
        L.polyline(ll, { color: "#e11", weight: 3, opacity: 0.9 }),
        L.circleMarker(ll[0], { radius: 5, color: "#080", fillOpacity: 1 }),
        L.circleMarker(ll[ll.length - 1], { radius: 5, color: "#a00", fillOpacity: 1 }),
      ]).addTo(map);
      map.fitBounds(L.polyline(ll).getBounds(), { padding: [20, 20] });
      status.textContent = `GPX: ${ll.length} points.`;
    } catch (err) { status.textContent = "GPX error: " + err.message; }
  };
  reader.readAsText(file);
});
```

- [ ] **Step 3: Verify + commit**

Load a GPX locally → red track + start/end markers; load an empty file → "no coordinates" message.
```bash
git add app/
git commit -m "feat(app): GPX route loader"
```

---

### Task 5: Mini-legend (reimplemented, collapsible)

**Goal:** A compact, flowable HTML/CSS legend in the controls pane, collapsible, faithful to the sheets.

**Files:**
- Modify: `app/index.html` (legend markup + CSS)
- Modify: `app/app.js` (collapse toggle)

**Acceptance Criteria:**
- [ ] Legend shows: trail difficulty (Easy=green, Moderate=blue, Most Difficult=black), road types (paved solid / gravel solid-gray / dirt dashed), special trails (seasonally-closed purple, ATV-prohibited orange), and key symbols (Trailhead, Campground, Restroom, Camp Site, Wilderness, Mileage ★) — matching `output/_leg_*.png`
- [ ] Legend collapses/expands via a toggle and reflows readably on a narrow (≤400px) screen

**Verify:** Narrow the browser to phone width; expand/collapse; compare swatches to `output/_leg_zoom.png` and `output/_leg_left.png`.

**Steps:**

- [ ] **Step 1: Add legend CSS to `app/index.html` `<style>`**

```css
    #legend { margin-top: 6px; }
    #legend h4 { margin: 6px 0 2px; font-size: 12px; }
    #legend .item { display: flex; align-items: center; gap: 6px; font-size: 12px; margin: 2px 0; }
    #legend .sw { width: 28px; height: 0; border-top: 3px solid #000; flex: 0 0 28px; }
    #legend .sw.dot { border-top: 3px dotted; }
    #legend .sw.dash { border-top: 3px dashed; }
    #legend .band { height: 10px; border-top: none; border-radius: 2px; }
    #legend .icon { width: 16px; height: 16px; flex: 0 0 16px; border-radius: 3px; color: #fff;
      font-size: 10px; line-height: 16px; text-align: center; }
    #legend.collapsed .body { display: none; }
```

- [ ] **Step 2: Add legend markup to `app/index.html`** (inside `#panel`, after the GPX row)

```html
    <div id="legend">
      <button id="legtoggle" type="button">Legend ▾</button>
      <div class="body">
        <h4>Motorized trails</h4>
        <div class="item"><span class="sw dot" style="border-color:#2e8b2e"></span>Easy</div>
        <div class="item"><span class="sw dot" style="border-color:#1565c0"></span>Moderate</div>
        <div class="item"><span class="sw dot" style="border-color:#000"></span>Most difficult</div>
        <div class="item"><span class="sw band" style="background:#9c5bbf"></span>Seasonally closed</div>
        <div class="item"><span class="sw band" style="background:#f5a623"></span>Class-1 ATV prohibited</div>
        <h4>Roads</h4>
        <div class="item"><span class="sw" style="border-color:#000"></span>Paved</div>
        <div class="item"><span class="sw" style="border-color:#888"></span>Gravel</div>
        <div class="item"><span class="sw dash" style="border-color:#888"></span>Dirt</div>
        <h4>Symbols</h4>
        <div class="item"><span class="icon" style="background:#6b4f2a">TH</span>Trailhead</div>
        <div class="item"><span class="icon" style="background:#6b4f2a">▲</span>Campground</div>
        <div class="item"><span class="icon" style="background:#d32f2f">▲</span>Camp site</div>
        <div class="item"><span class="icon" style="background:#d32f2f">WC</span>Restroom</div>
        <div class="item"><span class="sw" style="border-color:#7fb3d5"></span>Stream</div>
        <div class="item"><span class="icon" style="background:#bcd6ea;color:#333">≈</span>Wilderness</div>
        <div class="item"><span style="color:#a00;flex:0 0 28px;text-align:center">★</span>Mileage point</div>
      </div>
    </div>
```

- [ ] **Step 3: Append legend toggle to `app/app.js`**

```javascript
// ---- Mini-legend collapse toggle ----
(function legend() {
  const box = document.getElementById("legend");
  const btn = document.getElementById("legtoggle");
  btn.addEventListener("click", () => {
    box.classList.toggle("collapsed");
    btn.textContent = box.classList.contains("collapsed") ? "Legend ▸" : "Legend ▾";
  });
})();
```

- [ ] **Step 4: Verify + commit**

Narrow to ~380px; confirm legend reflows, swatches match the sheet, collapse/expand works.
```bash
git add app/
git commit -m "feat(app): compact collapsible mini-legend"
```

---

### Task 6: Deploy — build assets + GitHub Pages (end-to-end)

**Goal:** Publish `app/` via GitHub Pages from the public repo and confirm the installed PWA works offline on a real phone.

> **USER-ORDERED GATE — NON-SKIPPABLE.** This task was requested by the user in the current conversation. It MUST NOT be closed by walking around it, by declaring it "verified inline", or by substituting a cheaper check. Close only after every item in `acceptanceCriteria` has been re-validated independently, with output captured.

**Files:**
- Create: `.github/workflows/pages.yml` (deploys `app/` to Pages via Actions — folder-source Pages only allows `/` or `/docs`, so an Action is required to serve `app/`)
- Modify: `README.md` (Field viewer section: URL + one-time setup)
- (No new app code — assets already assembled in Tasks 1–5.)

**Acceptance Criteria:**
- [ ] `python tools/check_app_assets.py` passes; `app/map2016.webp` is ~3–5 MB
- [ ] Repo is public; GitHub Pages serves `app/` over HTTPS at `https://verstandinvictus.github.io/winom-frazier-geopdf/` (HTTP 200)
- [ ] On a real phone: open the URL → Add to Home Screen → launch → enable Airplane Mode → the map renders, the 2016/2025 toggle works, GPX loads, **and the live GPS blue dot appears and tracks** (the end-to-end offline test)
- [ ] README documents the one-time setup (open URL → Add to Home Screen → allow Location)

**Verify:** `curl -I https://verstandinvictus.github.io/winom-frazier-geopdf/` → 200; then the manual airplane-mode phone walkthrough above.

**Steps:**

- [ ] **Step 1: Re-run the asset check + confirm WebP size**

Run: `python tools/check_app_assets.py` → OK. Run: `python -c "from pathlib import Path; print(round(Path('app/map2016.webp').stat().st_size/1048576,1),'MB')"` → ~3–5 MB.

- [ ] **Step 2: Create the Pages deploy workflow** `.github/workflows/pages.yml`

```yaml
name: Deploy field viewer to Pages
on:
  push:
    branches: [main]
    paths: ["app/**", ".github/workflows/pages.yml"]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: app
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 3: Make the repo public + set Pages build source to Actions, then push to `main`**

```bash
gh repo edit VerstandInvictus/winom-frazier-geopdf --visibility public --accept-visibility-change-consequences
gh api -X POST repos/VerstandInvictus/winom-frazier-geopdf/pages -f build_type=workflow 2>/dev/null || \
  gh api -X PUT repos/VerstandInvictus/winom-frazier-geopdf/pages -f build_type=workflow 2>/dev/null || \
  echo "If both fail, set manually: repo Settings → Pages → Source: GitHub Actions"
# merge this feature branch to main (or run executing on main) so the workflow + app/ are on main, then push:
git push origin main
```
The workflow uploads `app/` as the Pages artifact, served at the project Pages root. Relative asset paths + `manifest` `scope:"."` make the `/winom-frazier-geopdf/` subpath work correctly.

- [ ] **Step 4: Confirm it serves**

Run (after the Pages Action finishes, ~1–2 min): `curl -I https://verstandinvictus.github.io/winom-frazier-geopdf/` → `HTTP/2 200`.

- [ ] **Step 5: Update `README.md`** — append:

```markdown
## Field viewer (offline PWA)
Open **https://verstandinvictus.github.io/winom-frazier-geopdf/** on your phone, then:
1. **Add to Home Screen** (Share → Add to Home Screen) — required for offline + GPS on iOS.
2. Launch it from the Home Screen icon and **allow Location**.
3. It caches the maps; after that it works fully offline with live GPS.
Toggle 2016/2025 maps, load a `.gpx`, and tap "Recenter on me."
```

- [ ] **Step 6: Real-phone end-to-end test (the gate)**

Open the URL on a phone → Add to Home Screen → launch → allow Location → enable Airplane Mode → confirm: map renders, 2016/2025 toggle works, GPX loads, **live blue dot appears and tracks**. Capture the result (note pass/fail per item).

- [ ] **Step 7: Commit**

```bash
git add README.md
git commit -m "docs+deploy: publish field-viewer PWA to GitHub Pages"
```

```json:metadata
{"files": ["README.md", "app/"], "verifyCommand": "curl -I https://verstandinvictus.github.io/winom-frazier-geopdf/ ; then real-phone airplane-mode walkthrough", "acceptanceCriteria": ["check_app_assets passes + webp ~3-5MB", "repo public + Pages serves app/ over HTTPS (200)", "real-phone airplane-mode: map+toggle+GPX+live GPS dot all work", "README setup documented"], "userGate": true, "tags": ["user-gate"]}
```

---

## Notes for execution

- **Branching:** this is a distinct feature; consider a branch off the current `feat/geopdf-toolkit` (or merge that PR to `main` first so Pages serves from `main`).
- **Run order:** Tasks 1→2→3→4→5→6 (2 depends on 1; 3/4/5 depend on 2; 6 depends on 3/4/5).
- **Testing reality:** this is a browser PWA — verification is Lighthouse + offline DevTools + the real-phone airplane-mode test, plus the `check_app_assets.py` automated guard against offline cache misses.
- **Asset commit:** `app/` (incl. `map2016.webp`, `vendor/`, JSON, SVG) is committed (the PWA must be self-contained on Pages) — do not gitignore it.
