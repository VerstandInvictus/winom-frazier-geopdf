// Georeferencing picker for 2025 guide page 2.
// Click trailheads on the rendered map; solve a pixel->lon/lat affine; export transform.json.
const W = 6400, H = 4300, DPI = 200;   // matches output/guide_page2_hi.png (200 DPI render)

// Pre-seeded control points from the map's own coordinate table (DMS -> decimal).
const points = [
  { name: "Winom TrailHead", lat: 45.011944, lon: -118.638611, px: null, py: null, marker: null, resid: null },
  { name: "Oriental TrailHead", lat: 44.975000, lon: -118.728611, px: null, py: null, marker: null, resid: null },
  { name: "Umapine OHV TrailHead", lat: 45.113889, lon: -118.561944, px: null, py: null, marker: null, resid: null },
];
let armed = 0;
let affine = null;

// ---- image map (pixel space, CRS.Simple) ----
const imgMap = L.map("imgmap", { crs: L.CRS.Simple, minZoom: -6, maxZoom: 4, zoomSnap: 0 });
const imgBounds = [[0, 0], [H, W]];
L.imageOverlay("./guide_page2_hi.png", imgBounds).addTo(imgMap);
imgMap.fitBounds(imgBounds);

const latlngToPx = (ll) => ({ px: ll.lng, py: H - ll.lat });
const pxToLatlng = (px, py) => [H - py, px];

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
  if (p.marker) {
    p.marker.setLatLng(pxToLatlng(px, py));
  } else {
    p.marker = L.marker(pxToLatlng(px, py), { draggable: true })
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

// ---- affine fit (least squares, 6 params) ----
function fit() {
  const pts = points.filter((p) => p.px != null && !Number.isNaN(p.lat) && !Number.isNaN(p.lon));
  const rmsEl = document.getElementById("rms");
  if (pts.length < 3) { affine = null; rmsEl.textContent = "RMS: need ≥3 placed points"; updatePreview(); return; }
  const AtA = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const AtLon = [0, 0, 0], AtLat = [0, 0, 0];
  for (const p of pts) {
    const r = [p.px, p.py, 1];
    for (let a = 0; a < 3; a++) {
      AtLon[a] += r[a] * p.lon;
      AtLat[a] += r[a] * p.lat;
      for (let b = 0; b < 3; b++) AtA[a][b] += r[a] * r[b];
    }
  }
  const inv = inv3(AtA);
  if (!inv) { affine = null; rmsEl.textContent = "RMS: points are collinear — spread them out"; return; }
  const cl = mul3(inv, AtLon), ca = mul3(inv, AtLat);
  affine = { a: cl[0], b: cl[1], c: cl[2], d: ca[0], e: ca[1], f: ca[2] };
  let sse = 0;
  for (const p of pts) {
    const [plon, plat] = applyAffine(p.px, p.py);
    p.resid = metersBetween(plat, plon, p.lat, p.lon);
    sse += p.resid * p.resid;
  }
  rmsEl.textContent = `RMS: ${Math.sqrt(sse / pts.length).toFixed(0)} m  (${pts.length} pts)`;
  updatePreview();
}

const applyAffine = (px, py) =>
  [affine.a * px + affine.b * py + affine.c, affine.d * px + affine.e * py + affine.f];

function updatePreview() {
  if (!document.getElementById("showprev").checked) return;
  ensurePrev();
  prevLayer.clearLayers();
  for (const p of points) {
    if (!Number.isNaN(p.lat) && p.lat != null)
      L.circleMarker([p.lat, p.lon], { radius: 5, color: "#080", fillOpacity: 1 })
        .bindTooltip(p.name + " (true)").addTo(prevLayer);
    if (p.px != null && affine) {
      const [plon, plat] = applyAffine(p.px, p.py);
      L.circleMarker([plat, plon], { radius: 4, color: "#e11", fillOpacity: 1 })
        .bindTooltip(p.name + " (fit)").addTo(prevLayer);
      L.polyline([[p.lat, p.lon], [plat, plon]], { color: "#e11", weight: 1 }).addTo(prevLayer);
    }
  }
  if (affine) {
    const corners = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => {
      const [lo, la] = applyAffine(x, y); return [la, lo];
    });
    L.polygon(corners, { color: "#06f", weight: 1, fill: false }).addTo(prevLayer);
    prevMap.fitBounds(L.polygon(corners).getBounds(), { padding: [10, 10] });
  }
}

// ---- 3x3 linear algebra ----
function inv3(m) {
  const [a, b, c] = m[0], [d, e, f] = m[1], [g, h, i] = m[2];
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  if (Math.abs(det) < 1e-12) return null;
  const id = 1 / det;
  return [
    [A * id, (c * h - b * i) * id, (b * f - c * e) * id],
    [B * id, (a * i - c * g) * id, (c * d - a * f) * id],
    [C * id, (b * g - a * h) * id, (a * e - b * d) * id],
  ];
}
const mul3 = (m, v) => [0, 1, 2].map((r) => m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2]);
const metersBetween = (la1, lo1, la2, lo2) => {
  const dy = (la2 - la1) * 111320;
  const dx = (lo2 - lo1) * 111320 * Math.cos((la1 * Math.PI) / 180);
  return Math.hypot(dx, dy);
};

// ---- table UI ----
function renderTable() {
  const tb = document.querySelector("#cptable tbody");
  tb.innerHTML = "";
  points.forEach((p, i) => {
    const tr = document.createElement("tr");
    if (i === armed) tr.classList.add("armed");
    tr.innerHTML =
      `<td>${i + 1}</td><td>${p.name}</td>` +
      `<td><input value="${p.lat ?? ""}" data-i="${i}" data-k="lat" size="8"></td>` +
      `<td><input value="${p.lon ?? ""}" data-i="${i}" data-k="lon" size="9"></td>` +
      `<td>${p.px == null ? "—" : `${Math.round(p.px)},${Math.round(p.py)}`}</td>` +
      `<td>${p.resid == null ? "—" : Math.round(p.resid)}</td>`;
    tr.addEventListener("click", (ev) => {
      if (ev.target.tagName !== "INPUT") { armed = i; renderTable(); }
    });
    tb.appendChild(tr);
  });
  tb.querySelectorAll("input").forEach((inp) => {
    inp.addEventListener("change", (e) => {
      points[+e.target.dataset.i][e.target.dataset.k] = parseFloat(e.target.value);
      fit();
    });
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
  const corners = [[0, 0], [W, 0], [W, H], [0, H]].map(([x, y]) => applyAffine(x, y)); // [lon,lat]
  const out = {
    image: "guide_page2_hi.png", image_size: [W, H], dpi: DPI,
    affine_px_to_lonlat: affine,
    control_points: points.filter((p) => p.px != null).map((p) => ({
      name: p.name, lat: p.lat, lon: p.lon, px: p.px, py: p.py, resid_m: p.resid,
    })),
    corners_lonlat: corners,
  };
  const blob = new Blob([JSON.stringify(out, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "transform.json";
  a.click();
});

document.getElementById("showprev").addEventListener("change", updatePreview);
renderTable();
