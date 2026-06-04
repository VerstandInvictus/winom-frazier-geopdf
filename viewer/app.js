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

// ---- GPX track overlay (compare a recorded ride against the map) ----
let gpxLayer = null;

function parseGpxLatLngs(xmlText) {
  const doc = new DOMParser().parseFromString(xmlText, "application/xml");
  if (doc.querySelector("parsererror")) throw new Error("invalid GPX/XML");
  // prefer track points, then route points, then bare waypoints
  let pts = [...doc.querySelectorAll("trkpt")];
  if (!pts.length) pts = [...doc.querySelectorAll("rtept")];
  if (!pts.length) pts = [...doc.querySelectorAll("wpt")];
  return pts
    .map((p) => [parseFloat(p.getAttribute("lat")), parseFloat(p.getAttribute("lon"))])
    .filter(([la, lo]) => !Number.isNaN(la) && !Number.isNaN(lo));
}

// ---- 2025 vector map (SVG overlay) ----
let svg2025 = null;
fetch("./page2_overlay.json")
  .then((r) => (r.ok ? r.json() : null))
  .then((meta) => {
    if (!meta) return;
    return fetch("./page2.svg").then((r) => r.text()).then((txt) => {
      const el = new DOMParser().parseFromString(txt, "image/svg+xml").documentElement;
      svg2025 = L.svgOverlay(el, meta.bounds, { opacity: 0.95, interactive: false });
      document.getElementById("svg2025").addEventListener("change", (e) => {
        if (e.target.checked) { svg2025.addTo(map); map.fitBounds(meta.bounds); }
        else map.removeLayer(svg2025);
      });
    });
  })
  .catch(() => {});

document.getElementById("gpx").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const latlngs = parseGpxLatLngs(reader.result);
      if (!latlngs.length) {
        status.textContent =
          "GPX has no <trkpt>/<rtept>/<wpt> coordinates — the route wasn't included.";
        return;
      }
      if (gpxLayer) gpxLayer.remove();
      gpxLayer = L.layerGroup([
        L.polyline(latlngs, { color: "#e11", weight: 3, opacity: 0.9 }),
        L.circleMarker(latlngs[0], { radius: 5, color: "#080", fillOpacity: 1 }).bindPopup("Track start"),
        L.circleMarker(latlngs[latlngs.length - 1], { radius: 5, color: "#a00", fillOpacity: 1 }).bindPopup("Track end"),
      ]).addTo(map);
      map.fitBounds(L.polyline(latlngs).getBounds(), { padding: [20, 20] });
      status.textContent = `GPX loaded: ${latlngs.length} track points (red). Compare against the map overlay.`;
    } catch (err) {
      status.textContent = "GPX error: " + err.message;
    }
  };
  reader.readAsText(file);
});
