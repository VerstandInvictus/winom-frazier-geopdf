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
