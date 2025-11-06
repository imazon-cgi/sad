// sw.js — Stale-While-Revalidate para /dataset/ e tiles (Carto/OSM)
const CACHE = 'gpx-sad-v1';
const SWR_PATHS = [
  /^https?:\/\/[^\/]+\/dataset\//,
  /^https?:\/\/[a-d]\.basemaps\.cartocdn\.com\//,
  /^https?:\/\/.*tile\.openstreetmap\.org\//
];

self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = req.url;
  if (!SWR_PATHS.some(rx => rx.test(url))) return;

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(req, { ignoreVary: true });

    // SWR: responde do cache se houver e revalida em background
    const network = fetch(req).then(res => {
      if (res.ok) cache.put(req, res.clone());
      return res;
    }).catch(() => cached || Response.error());

    return cached || network;
  })());
});
