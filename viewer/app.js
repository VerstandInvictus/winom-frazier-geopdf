// Crisp, fast trail-map viewer: the corrected 2016 map rendered directly as a rotated
// image overlay (like the picker — no georaster resampling, no basemap), plus a
// simulated/live GPS marker, a GPX track loader, and the optional 2025 vector overlay.
const map = L.map("map");
const status = document.getElementById("status");
let overlay = null, simMarker = null, liveMarker = null, watchId = null, gpxLayer = null, svg2025 = null;

// ---- 2016 trail map: rotated image overlay (full native resolution) ----
fetch("./overlay2016.json")
  .then((r) => r.json())
  .then((o) => {
    const tl = L.latLng(o.topleft), tr = L.latLng(o.topright), bl = L.latLng(o.bottomleft);
    overlay = L.imageOverlay.rotated("./" + o.image, tl, tr, bl, { opacity: 1, interactive: false }).addTo(map);
    const br = L.latLng(tr.lat + bl.lat - tl.lat, tr.lng + bl.lng - tl.lng);
    map.fitBounds(L.latLngBounds([tl, tr, bl, br]));
    status.textContent = "2016 map loaded.";
  })
  .catch((e) => { status.textContent = "map load error: " + e.message; });

document.getElementById("opacity").addEventListener("input", (e) => {
  if (overlay) overlay.setOpacity(parseFloat(e.target.value));
});

// ---- simulated GPS ----
document.getElementById("gps-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const lat = parseFloat(document.getElementById("lat").value);
  const lon = parseFloat(document.getElementById("lon").value);
  if (Number.isNaN(lat) || Number.isNaN(lon)) return;
  if (simMarker) simMarker.setLatLng([lat, lon]);
  else simMarker = L.circleMarker([lat, lon], { radius: 7, color: "#06f", fillColor: "#06f", fillOpacity: 0.9 })
    .addTo(map).bindPopup("Simulated GPS");
  simMarker.openPopup();
  map.panTo([lat, lon]);
});

// ---- live GPS ----
document.getElementById("track").addEventListener("change", (e) => {
  if (e.target.checked) {
    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude, longitude } = pos.coords;
        if (liveMarker) liveMarker.setLatLng([latitude, longitude]);
        else liveMarker = L.circleMarker([latitude, longitude], { radius: 7, color: "red", fillColor: "red", fillOpacity: 0.9 })
          .addTo(map).bindPopup("Live GPS");
        map.panTo([latitude, longitude]);
      },
      (err) => { status.textContent = "Geolocation: " + err.message; },
      { enableHighAccuracy: true },
    );
  } else if (watchId != null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
});

// ---- GPX track overlay (compare a recorded ride against the map) ----
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
      const latlngs = parseGpxLatLngs(reader.result);
      if (!latlngs.length) { status.textContent = "GPX has no <trkpt>/<rtept>/<wpt> coordinates."; return; }
      if (gpxLayer) gpxLayer.remove();
      gpxLayer = L.layerGroup([
        L.polyline(latlngs, { color: "#e11", weight: 3, opacity: 0.9 }),
        L.circleMarker(latlngs[0], { radius: 5, color: "#080", fillOpacity: 1 }).bindPopup("Track start"),
        L.circleMarker(latlngs[latlngs.length - 1], { radius: 5, color: "#a00", fillOpacity: 1 }).bindPopup("Track end"),
      ]).addTo(map);
      map.fitBounds(L.polyline(latlngs).getBounds(), { padding: [20, 20] });
      status.textContent = `GPX loaded: ${latlngs.length} track points (red).`;
    } catch (err) { status.textContent = "GPX error: " + err.message; }
  };
  reader.readAsText(file);
});

// ---- 2025 vector overlay (SVG) ----
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
