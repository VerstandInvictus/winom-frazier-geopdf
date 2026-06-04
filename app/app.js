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
