// Bump CACHE_VERSION whenever the ASSETS list changes (forces clients to re-cache).
const CACHE_VERSION = "wf-v16";
const ASSETS = [
  "./", "./index.html", "./app.js", "./manifest.webmanifest",
  "./icons/icon-192.png", "./icons/icon-512.png",
  "./vendor/leaflet.js", "./vendor/leaflet.css", "./vendor/Leaflet.ImageOverlay.Rotated.js",
  "./vendor/protomaps-leaflet.js",
  "./world.pmtiles", "./westus.pmtiles",
  "./map2016.webp", "./overlay2016.json", "./page2.svg", "./page2_overlay.json",
  "./desolation.webp", "./desolation_overlay.json",
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
// Serve byte-range requests for the .pmtiles archive from the cached full file (offline).
const _pmBufs = {};
async function pmtilesBuffer(href) {
  if (_pmBufs[href]) return _pmBufs[href];
  const cache = await caches.open(CACHE_VERSION);
  let res = await cache.match(href);
  if (!res) { res = await fetch(href); try { await cache.put(href, res.clone()); } catch (e) {} }
  _pmBufs[href] = await res.arrayBuffer();
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
