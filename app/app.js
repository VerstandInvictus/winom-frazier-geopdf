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
