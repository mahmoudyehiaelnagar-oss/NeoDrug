/**
 * Neo Drug service worker.
 *
 * Strategy: network-first for the app shell so deployments are picked up
 * immediately, with an offline cache fallback. API responses are never cached
 * (they may contain private account data).
 */
const CACHE_NAME = "neo-drug-shell-v1";
const SHELL_FILES = [
  "./index.html",
  "./drugs.html",
  "./checker.html",
  "./ai.html",
  "./detail.html",
  "./sync.html",
  "./manifest.json",
  "./api.js",
  "./auth-pro.js",
  "./creative-background.js",
  "./creative-theme.css",
  "./icon-192.png",
  "./icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      // Ignore individual failures so a single missing asset cannot break install.
      Promise.allSettled(SHELL_FILES.map((file) => cache.add(file)))
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response && response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      })
      .catch(() => caches.match(request).then((cached) => cached || caches.match("./index.html")))
  );
});
