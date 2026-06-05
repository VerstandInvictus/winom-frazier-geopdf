// Bump CACHE_VERSION whenever the ASSETS list changes (forces clients to re-cache).
const CACHE_VERSION = "wf-v32";
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

// The big maps are NOT precached in install(): the .pmtiles are fetched-in-full and cached by the
// range handler on first use; the trail maps cache on first fetch + via the "precache-maps" message.
const DEFER = ["./world.pmtiles", "./westus.pmtiles", "./map2016.webp", "./page2.svg", "./desolation.webp", "./heppner.webp"];
const PRECACHE = ASSETS.filter((u) => !DEFER.includes(u));

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_VERSION)
      .then((c) => c.addAll(PRECACHE.map((u) => new Request(u, { cache: "no-cache" }))))
      .then(() => self.skipWaiting())
  );
});
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// GitHub Pages serves .pmtiles gzip-encoded, so a byte-range request to Pages returns a range of the
// GZIPPED stream tagged Content-Encoding: gzip -- the browser can't decode a partial gzip
// (ERR_CONTENT_DECODING_FAILED) and the offsets are wrong anyway. So NEVER range-request Pages:
// fetch the whole file once (the browser decodes gzip), cache the raw bytes, and slice ranges from
// that decoded copy. _pmFull dedupes concurrent callers to a single download.
const _pmFull = {};
function pmtilesFull(href) {
  if (!_pmFull[href]) {
    _pmFull[href] = (async () => {
      const c = await caches.open(CACHE_VERSION);
      const hit = await c.match(href);
      if (hit) return hit.arrayBuffer();
      const res = await fetch(new Request(href, { cache: "no-store" })); // fresh; browser decodes gzip
      const buf = await res.arrayBuffer();
      try { await c.put(href, new Response(buf, { headers: { "Content-Type": "application/octet-stream" } })); } catch (err) {}
      return buf;
    })().catch((err) => { delete _pmFull[href]; throw err; });
  }
  return _pmFull[href];
}
function cacheMapsForOffline() {
  return Promise.all(DEFER.map(async (u) => {
    const href = new URL(u, self.registration.scope).href;
    try {
      if (href.endsWith(".pmtiles")) { await pmtilesFull(href); return; }
      const c = await caches.open(CACHE_VERSION);
      if (!(await c.match(u))) await c.add(new Request(u, { cache: "no-cache" }));
    } catch (err) { /* retry next load */ }
  }));
}
self.addEventListener("message", (e) => {
  if (e.data === "version" && e.source) e.source.postMessage({ version: CACHE_VERSION });
  if (e.data === "precache-maps") e.waitUntil(cacheMapsForOffline());
});

self.addEventListener("fetch", (e) => {
  if (e.request.method !== "GET") return;
  const url = new URL(e.request.url);
  if (url.pathname.endsWith(".pmtiles")) {
    e.respondWith((async () => {
      const buf = await pmtilesFull(url.href); // decoded full file, from cache or one download
      const range = e.request.headers.get("range");
      if (!range) {
        return new Response(buf, {
          status: 200,
          headers: { "Content-Length": String(buf.byteLength), "Accept-Ranges": "bytes", "Content-Type": "application/octet-stream" },
        });
      }
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
