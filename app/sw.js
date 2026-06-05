// Bump CACHE_VERSION whenever the ASSETS list changes (forces clients to re-cache).
const CACHE_VERSION = "wf-v27";
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

self.addEventListener("install", (e) => {
  // cache:"no-cache" revalidates each precache fetch with the server (ETag), so a new version
  // never re-stores a stale file from the browser HTTP cache (GitHub Pages' max-age=600).
  // Unchanged big maps return 304 (no re-download) -- only changed files re-fetch.
  e.waitUntil(
    caches.open(CACHE_VERSION)
      .then((c) => c.addAll(ASSETS.map((u) => new Request(u, { cache: "no-cache" }))))
      .then(() => self.skipWaiting())
  );
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
// Serve byte-range requests for the .pmtiles archive from the cached full file (offline).
const _pmBufs = {};
function pmtilesBuffer(href) {
  // Cache the PROMISE (not the resolved buffer) so concurrent range requests for the same
  // .pmtiles share ONE fetch. Otherwise, before the file is cached (e.g. during install), each
  // tile triggers a full re-download and the racing duplicates fail ("Failed to fetch").
  if (!_pmBufs[href]) {
    _pmBufs[href] = (async () => {
      const cache = await caches.open(CACHE_VERSION);
      let res = await cache.match(href);
      if (!res) { res = await fetch(href); try { await cache.put(href, res.clone()); } catch (e) {} }
      return res.arrayBuffer();
    })().catch((e) => { delete _pmBufs[href]; throw e; }); // clear on failure -> allow retry
  }
  return _pmBufs[href];
}
self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  const range = e.request.headers.get("range");
  if (url.pathname.endsWith(".pmtiles") && range) {
    e.respondWith((async () => {
      const buf = await pmtilesBuffer(url.href);
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
