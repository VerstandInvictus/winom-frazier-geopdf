// Bump CACHE_VERSION whenever the ASSETS list changes (forces clients to re-cache).
const CACHE_VERSION = "wf-v29";
const ASSETS = [
  "./", "./index.html", "./app.js", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png", "./icons/icon-512-maskable.png",
  "./favicon.svg", "./favicon.ico", "./apple-touch-icon.png",
  "./vendor/leaflet.js", "./vendor/leaflet.css", "./vendor/Leaflet.ImageOverlay.Rotated.js",
  "./vendor/protomaps-leaflet.js",
  "./world.pmtiles", "./westus.pmtiles",
  "./map2016.webp", "./overlay2016.json", "./page2.svg", "./page2_overlay.json",
  "./desolation.webp", "./desolation_overlay.json",
  "./heppner.webp", "./heppner_overlay.json",
];

// Big maps: default cache (served from the HTTP cache when unchanged -> fast, no 40 MB
// re-download that would saturate the connection and break in-flight basemap fetches).
// Everything else is small and revalidated (cache:"no-cache") so updates are always fresh.
const DATA = ["./world.pmtiles", "./westus.pmtiles", "./map2016.webp", "./page2.svg", "./desolation.webp", "./heppner.webp"];
const CODE = ASSETS.filter((u) => !DATA.includes(u));

// href -> promise that resolves when that big map finishes precaching, so the fetch handler can
// WAIT for the install's single download instead of starting a competing one (which the browser
// would cancel -> "Failed to fetch" at low zoom while installing).
const _ready = {};
self.addEventListener("install", (e) => {
  e.waitUntil((async () => {
    const c = await caches.open(CACHE_VERSION);
    await c.addAll(CODE.map((u) => new Request(u, { cache: "no-cache" }))); // small + always fresh
    // Precache big maps in the background (world first) so the worker takes control immediately;
    // the fetch handler coordinates via _ready rather than blocking on this.
    (async () => {
      for (const u of DATA) {
        const href = new URL(u, self.registration.scope).href;
        _ready[href] = c.add(u).catch(() => {});
        await _ready[href];
      }
    })();
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});
// Report the running cache version to the page (so it can show which build is live).
self.addEventListener("message", (e) => {
  if (e.data === "version" && e.source) e.source.postMessage({ version: CACHE_VERSION });
});
// .pmtiles byte-range reads: if the file is cached, slice from an in-memory copy (offline). If
// it is not cached yet (mid-install), pass the range request straight to the network -- GitHub
// Pages serves ranges natively, and pulling the whole file here would duplicate the install's
// download (the browser cancels one -> "Failed to fetch").
const _pmBufs = {};
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  const range = e.request.headers.get("range");
  if (url.pathname.endsWith(".pmtiles") && range) {
    e.respondWith((async () => {
      if (_ready[url.href]) { try { await _ready[url.href]; } catch (_) {} } // wait for the install's download
      if (!_pmBufs[url.href]) {
        _pmBufs[url.href] = caches.open(CACHE_VERSION)
          .then((c) => c.match(url.href))
          .then((hit) => (hit ? hit.arrayBuffer() : null));
      }
      const buf = await _pmBufs[url.href].catch(() => null);
      if (!buf) { delete _pmBufs[url.href]; return fetch(e.request); } // not cached yet -> network range
      const m = /bytes=(\d+)-(\d*)/.exec(range);
      const start = +m[1];
      const end = m[2] ? +m[2] : buf.byteLength - 1;
      const slice = buf.slice(start, end + 1);
      return new Response(slice, {
        status: 206,
        headers: {
          "Content-Range": `bytes ${start}-${end}/${buf.byteLength}`,
          "Content-Length": String(slice.byteLength),
          "Accept-Ranges": "bytes",
          "Content-Type": "application/octet-stream",
        },
      });
    })());
    return;
  }
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request).then((resp) => {
      const copy = resp.clone();
      caches.open(CACHE_VERSION).then((c) => c.put(e.request, copy)).catch(() => {});
      return resp;
    }).catch(() => caches.match("./index.html")))
  );
});
