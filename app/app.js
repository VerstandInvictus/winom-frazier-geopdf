// ---- PWA bootstrap: service worker, persistent storage, install hint ----
if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("./sw.js").catch((e) => console.warn("SW register failed", e));
}
if (navigator.storage && navigator.storage.persist) {
  navigator.storage.persist().then((granted) => console.log("persistent storage:", granted));
}
// Install: a real "Install app" button on Android/Chrome (fires the WebAPK install, not a
// bookmark shortcut) via beforeinstallprompt; iOS Safari has no such API, so it falls back to
// the Share -> Add to Home Screen instruction.
(function install() {
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone;
  const hint = document.getElementById("install-hint");
  if (!hint || standalone || localStorage.getItem("wf-hint-dismissed")) return;
  const btn = document.getElementById("install-btn");
  const iosText = document.getElementById("install-ios");
  const arrow = document.getElementById("install-arrow");
  let deferred = null;

  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();          // keep Chrome from auto-showing its mini-infobar
    deferred = e;
    iosText.hidden = true;
    arrow.hidden = true;
    btn.hidden = false;
    hint.hidden = false;
  });
  btn.addEventListener("click", async () => {
    if (!deferred) return;
    deferred.prompt();           // the real install dialog (WebAPK)
    await deferred.userChoice;
    deferred = null;
    hint.hidden = true;
  });
  window.addEventListener("appinstalled", () => { hint.hidden = true; });
  document.getElementById("install-dismiss").addEventListener("click", () => {
    hint.hidden = true;
    localStorage.setItem("wf-hint-dismissed", "1");
  });

  // iOS Safari has no beforeinstallprompt -> point an arrow at the Share button.
  const isIOS = ["iPhone", "iPad", "iPod"].includes(navigator.platform) ||
    /iphone|ipad|ipod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (isIOS) { iosText.hidden = false; arrow.hidden = false; btn.hidden = true; hint.hidden = false; }
})();

// ---- Map core: 2016 raster (rotated overlay) + 2025 vector (SVG), toggle ----
const map = L.map("map", { zoomControl: true });
// Base maps go in a dedicated pane BELOW the default overlayPane, so the GPX track
// and GPS dot (in overlayPane) always render on top and never get hidden by a map swap.
map.createPane("basemaps");
map.getPane("basemaps").style.zIndex = 250;
// Desolation sits in its own pane just above the Winom maps so it stays on top where the two
// sheets' edges graze each other (still below the GPX/GPS panes).
map.createPane("desolation");
map.getPane("desolation").style.zIndex = 255;
map.createPane("heppner");
map.getPane("heppner").style.zIndex = 256;
const status = document.getElementById("status");

// ---- Offline vector basemap: global base + western-US detail ----
// Two protomaps-leaflet layers, each in its own pane below the trail maps (250) and clear of
// Leaflet's tilePane (200). The detail layer is constrained with bounds + minZoom so it ONLY
// creates tiles inside its region; otherwise it paints empty opaque tiles that flash and cover
// the world layer. minZoom is 7 (= source-min 6 + the renderer's levelDiff of 1): at its first
// zoom the layer fetches data one level coarser, so starting at z6 would request z5 (below the
// source's z6 floor) and draw a blank tile — the gray band at the boundary. maxDataZoom lets a
// layer overzoom past its deepest tiles. The world layer (z0-5) shows below z7 and outside the bbox.
const WEST_BOUNDS = L.latLngBounds([[38, -125], [49.5, -109]]); // westus.pmtiles extent
const BG_TIERS = [
  { url: "world.pmtiles", pane: "bg-world", zIndex: 240, opts: { maxDataZoom: 5 } },
  { url: "westus.pmtiles", pane: "bg-west", zIndex: 245, opts: { maxDataZoom: 10, minZoom: 7, bounds: WEST_BOUNDS } },
];
for (const t of BG_TIERS) {
  map.createPane(t.pane);
  map.getPane(t.pane).style.zIndex = t.zIndex;
  try {
    protomapsL.leafletLayer(Object.assign({ url: t.url, flavor: "grayscale", lang: "en", pane: t.pane }, t.opts)).addTo(map);
  } catch (e) { console.warn("basemap layer failed:", t.url, e); }
}
let layer2016 = null, layer2025 = null, layerDes = null, layerHep = null, activeWinom = null;
let bounds2016 = null, bounds2025 = null, boundsDes = null;

// 2016 and 2025 cover the same Winom-Frazier area -> mutually exclusive toggle. Desolation is
// a separate area to the SW that never overlaps, so it stays on; its button just flies there.
function showWinom(which) {
  if (layer2016 && map.hasLayer(layer2016)) map.removeLayer(layer2016);
  if (layer2025 && map.hasLayer(layer2025)) map.removeLayer(layer2025);
  const [layer, bounds] = which === "2016" ? [layer2016, bounds2016] : [layer2025, bounds2025];
  if (layer) { layer.addTo(map); map.fitBounds(bounds); activeWinom = which; }
  document.getElementById("m2016").classList.toggle("on", activeWinom === "2016");
  document.getElementById("m2025").classList.toggle("on", activeWinom === "2025");
}

Promise.all([
  fetch("overlay2016.json").then((r) => r.json()),
  fetch("page2_overlay.json").then((r) => r.json()),
  fetch("page2.svg").then((r) => r.text()),
  fetch("desolation_overlay.json").then((r) => r.json()),
  fetch("heppner_overlay.json").then((r) => r.json()),
]).then(([o16, o25, svg25, oDes, oHep]) => {
  const tl = L.latLng(o16.topleft), tr = L.latLng(o16.topright), bl = L.latLng(o16.bottomleft);
  const br = L.latLng(tr.lat + bl.lat - tl.lat, tr.lng + bl.lng - tl.lng);
  layer2016 = L.imageOverlay.rotated("map2016.webp", tl, tr, bl, { opacity: 1, interactive: false, pane: "basemaps" });
  bounds2016 = L.latLngBounds([tl, tr, bl, br]);
  layer2025 = L.svgOverlay(new DOMParser().parseFromString(svg25, "image/svg+xml").documentElement,
    o25.bounds, { opacity: 1, interactive: false, pane: "basemaps" });
  bounds2025 = L.latLngBounds(o25.bounds);
  // Desolation: rotated raster overlay (its topo base is CMYK JPEGs that render dark as SVG).
  const dtl = L.latLng(oDes.topleft), dtr = L.latLng(oDes.topright), dbl = L.latLng(oDes.bottomleft);
  const dbr = L.latLng(dtr.lat + dbl.lat - dtl.lat, dtr.lng + dbl.lng - dtl.lng);
  layerDes = L.imageOverlay.rotated("desolation.webp", dtl, dtr, dbl, { opacity: 1, interactive: false, pane: "desolation" });
  boundsDes = L.latLngBounds([dtl, dtr, dbl, dbr]);
  layerDes.addTo(map); // Desolation is a separate area -> always shown
  // Heppner: another geocoded area ~80 km west, also a rotated raster, also always shown.
  const htl = L.latLng(oHep.topleft), htr = L.latLng(oHep.topright), hbl = L.latLng(oHep.bottomleft);
  layerHep = L.imageOverlay.rotated("heppner.webp", htl, htr, hbl, { opacity: 1, interactive: false, pane: "heppner" });
  layerHep.addTo(map);
  showWinom("2016");
  status.textContent = ""; // clear "Loading…" (the row collapses when empty)
}).catch((e) => { status.textContent = "Map load error: " + e.message; });

document.getElementById("m2016").addEventListener("click", () => showWinom("2016"));
document.getElementById("m2025").addEventListener("click", () => showWinom("2025"));

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

// ---- Mini-legend + GeoPDFs collapse toggles ----
(function toggles() {
  const box = document.getElementById("legend");
  const legBtn = document.getElementById("legtoggle");
  legBtn.addEventListener("click", () => {
    box.classList.toggle("collapsed");
    legBtn.textContent = box.classList.contains("collapsed") ? "Legend ▸" : "Legend ▾";
  });
  const pdfBtn = document.getElementById("pdftoggle");
  const links = document.getElementById("pdflinks");
  pdfBtn.addEventListener("click", () => {
    links.hidden = !links.hidden;
    pdfBtn.textContent = links.hidden ? "GeoPDFs ▸" : "GeoPDFs ▾";
  });
})();
