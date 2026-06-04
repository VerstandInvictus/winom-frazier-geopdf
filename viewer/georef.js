// Georeferencing picker. Works on the 2025 page-2 sheet (default) or the 2016 map (?map=2016).
// Click trailheads -> solve a pixel->lon/lat affine. If the map has an existing georeference,
// also report that georeference's error at the same points (so we can compare before re-pinning).

const TRAILHEADS = [
  { name: "Winom TrailHead", lat: 45.011944, lon: -118.638611 },
  { name: "Oriental TrailHead", lat: 44.975000, lon: -118.728611 },
  { name: "Umapine OHV TrailHead", lat: 45.113889, lon: -118.561944 },
  { name: "Frazier TrailHead", lat: 45.1597, lon: -118.6397 },
  { name: "Tower Mtn Lookout", lat: 45.05422652503636, lon: -118.56829504301199 },
];
const MAPS = {
  "2025": { img: "guide_page2_northup.png", W: 6400, H: 4300, rotated: true },
  "2016": { img: "map2016.png", W: 3873, H: 4523, rotated: false, existing: "map2016_existing.json" },
};
const which = new URLSearchParams(location.search).get("map") === "2016" ? "2016" : "2025";
const cfg = MAPS[which];
const W = cfg.W, H = cfg.H;
const DW = cfg.rotated ? H : W, DH = cfg.rotated ? W : H;   // display dims (rotated 90° CCW for 2025)
document.getElementById("maptitle").textContent = `Georeference: ${which} map`;

const points = TRAILHEADS.map((t) => ({ ...t, px: null, py: null, marker: null, resid: null }));
let armed = 0, affine = null, existing = null;

if (cfg.existing) {
  fetch("./" + cfg.existing).then((r) => (r.ok ? r.json() : null))
    .then((j) => { existing = j && j.affine; renderTable(); fit(); }).catch(() => {});
}

// ---- image map (CRS.Simple) ----
const imgMap = L.map("imgmap", { crs: L.CRS.Simple, minZoom: -6, maxZoom: 4, zoomSnap: 0 });
L.imageOverlay("./" + cfg.img, [[0, 0], [DH, DW]]).addTo(imgMap);
imgMap.fitBounds([[0, 0], [DH, DW]]);
const pinIcon = L.divIcon({ className: "cp-pin", html: "<div></div>", iconSize: [16, 16], iconAnchor: [8, 8] });

function latlngToPx(ll) {
  if (cfg.rotated) { const dy = DH - ll.lat; return { px: (W - 1) - dy, py: ll.lng }; }
  return { px: ll.lng, py: DH - ll.lat };
}
function pxToLatlng(px, py) {
  if (cfg.rotated) { const dy = (W - 1) - px; return [DH - dy, py]; }
  return [DH - py, px];
}

imgMap.on("click", (e) => {
  if (armed == null || armed >= points.length) return;
  const { px, py } = latlngToPx(e.latlng);
  setPixel(armed, px, py);
  const next = points.findIndex((p) => p.px == null);
  armed = next === -1 ? null : next;
  renderTable();
});

function setPixel(i, px, py) {
  const p = points[i];
  p.px = px; p.py = py;
  if (p.marker) p.marker.setLatLng(pxToLatlng(px, py));
  else {
    p.marker = L.marker(pxToLatlng(px, py), { draggable: true, icon: pinIcon })
      .addTo(imgMap).bindTooltip(p.name, { permanent: true, direction: "top" });
    p.marker.on("drag dragend", (ev) => {
      const q = latlngToPx(ev.target.getLatLng());
      p.px = q.px; p.py = q.py; fit(); renderTable();
    });
  }
  fit();
}

// ---- geographic preview ----
let prevMap = null, prevLayer = null;
function ensurePrev() {
  if (prevMap) return;
  prevMap = L.map("prevmap").setView([45.05, -118.62], 10);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OSM" }).addTo(prevMap);
  prevLayer = L.layerGroup().addTo(prevMap);
}

// ---- affine fit ----
function existAt(p) {
  if (!existing || p.px == null) return null;
  const lon = existing.a * p.px + existing.b * p.py + existing.c;
  const lat = existing.d * p.px + existing.e * p.py + existing.f;
  return metersBetween(lat, lon, p.lat, p.lon);
}

function fit() {
  const pts = points.filter((p) => p.px != null && !Number.isNaN(p.lat) && !Number.isNaN(p.lon));
  const rmsEl = document.getElementById("rms");
  if (pts.length >= 3) {
    const AtA = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], AtLon = [0, 0, 0], AtLat = [0, 0, 0];
    for (const p of pts) {
      const r = [p.px, p.py, 1];
      for (let a = 0; a < 3; a++) {
        AtLon[a] += r[a] * p.lon; AtLat[a] += r[a] * p.lat;
        for (let b = 0; b < 3; b++) AtA[a][b] += r[a] * r[b];
      }
    }
    const inv = inv3(AtA);
    if (inv) {
      const cl = mul3(inv, AtLon), ca = mul3(inv, AtLat);
      affine = { a: cl[0], b: cl[1], c: cl[2], d: ca[0], e: ca[1], f: ca[2] };
      let sse = 0;
      for (const p of pts) { const [plon, plat] = applyAffine(p.px, p.py); p.resid = metersBetween(plat, plon, p.lat, p.lon); sse += p.resid * p.resid; }
      rmsEl.textContent = `new-fit RMS: ${Math.sqrt(sse / pts.length).toFixed(0)} m (${pts.length} pts)`;
    } else { affine = null; rmsEl.textContent = "RMS: points collinear"; }
  } else { affine = null; rmsEl.textContent = "new-fit RMS: need ≥3 points"; }
  // existing georeference RMS at the same points
  const exEl = document.getElementById("existrms");
  if (existing) {
    const errs = pts.map(existAt).filter((v) => v != null);
    exEl.textContent = errs.length
      ? `existing georef RMS: ${Math.sqrt(errs.reduce((s, v) => s + v * v, 0) / errs.length).toFixed(0)} m`
      : "existing georef RMS: —";
  } else exEl.textContent = "";
  updatePreview();
}

const applyAffine = (px, py) => [affine.a * px + affine.b * py + affine.c, affine.d * px + affine.e * py + affine.f];

function updatePreview() {
  if (!document.getElementById("showprev").checked) return;
  ensurePrev();
  prevLayer.clearLayers();
  for (const p of points) {
    if (!Number.isNaN(p.lat))
      L.circleMarker([p.lat, p.lon], { radius: 5, color: "#080", fillOpacity: 1 }).bindTooltip(p.name + " (true)").addTo(prevLayer);
    if (p.px != null && affine) {
      const [plon, plat] = applyAffine(p.px, p.py);
      L.circleMarker([plat, plon], { radius: 4, color: "#e11", fillOpacity: 1 }).bindTooltip(p.name + " (fit)").addTo(prevLayer);
      L.polyline([[p.lat, p.lon], [plat, plon]], { color: "#e11", weight: 1 }).addTo(prevLayer);
    }
  }
  if (affine) {
    const corners = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => { const [lo, la] = applyAffine(x, y); return [la, lo]; });
    L.polygon(corners, { color: "#06f", weight: 1, fill: false }).addTo(prevLayer);
    prevMap.fitBounds(L.polygon(corners).getBounds(), { padding: [10, 10] });
  }
}

// ---- helpers ----
function inv3(m) {
  const [a, b, c] = m[0], [d, e, f] = m[1], [g, h, i] = m[2];
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-12) return null;
  const id = 1 / det;
  return [[A * id, (c * h - b * i) * id, (b * f - c * e) * id],
          [B * id, (a * i - c * g) * id, (c * d - a * f) * id],
          [C * id, (b * g - a * h) * id, (a * e - b * d) * id]];
}
const mul3 = (m, v) => [0, 1, 2].map((r) => m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2]);
const metersBetween = (la1, lo1, la2, lo2) => {
  const dy = (la2 - la1) * 111320, dx = (lo2 - lo1) * 111320 * Math.cos((la1 * Math.PI) / 180);
  return Math.hypot(dx, dy);
};

// ---- table ----
function renderTable() {
  const tb = document.querySelector("#cptable tbody");
  tb.innerHTML = "";
  points.forEach((p, i) => {
    const tr = document.createElement("tr");
    if (i === armed) tr.classList.add("armed");
    const ex = existAt(p);
    tr.innerHTML =
      `<td>${i + 1}</td><td>${p.name}</td>` +
      `<td><input value="${p.lat ?? ""}" data-i="${i}" data-k="lat" size="8"></td>` +
      `<td><input value="${p.lon ?? ""}" data-i="${i}" data-k="lon" size="9"></td>` +
      `<td>${p.px == null ? "—" : `${Math.round(p.px)},${Math.round(p.py)}`}</td>` +
      `<td>${p.resid == null ? "—" : Math.round(p.resid)}</td>` +
      `<td>${ex == null ? "" : Math.round(ex)}</td>`;
    tr.addEventListener("click", (ev) => { if (ev.target.tagName !== "INPUT") { armed = i; renderTable(); } });
    tb.appendChild(tr);
  });
  tb.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("change", (e) => { points[+e.target.dataset.i][e.target.dataset.k] = parseFloat(e.target.value); fit(); renderTable(); });
  });
}

document.getElementById("addbtn").addEventListener("click", () => {
  const name = prompt("Point name (type its lat/lon in the table after):", "Custom point");
  if (name == null) return;
  points.push({ name, lat: NaN, lon: NaN, px: null, py: null, marker: null, resid: null });
  if (armed == null) armed = points.length - 1;
  renderTable();
});

document.getElementById("exportbtn").addEventListener("click", () => {
  if (!affine) { alert("Place ≥3 points with valid coords first."); return; }
  const corners = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => applyAffine(x, y));
  const out = {
    map: which, image: cfg.img, image_size: [W, H], dpi: 200, affine_px_to_lonlat: affine,
    control_points: points.filter((p) => p.px != null).map((p) => ({ name: p.name, lat: p.lat, lon: p.lon, px: p.px, py: p.py, resid_m: p.resid })),
    corners_lonlat: corners,
  };
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = `transform_${which}.json`; a.click();
});

document.getElementById("showprev").addEventListener("change", updatePreview);
renderTable();
