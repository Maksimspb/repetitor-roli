// Service worker: офлайн-кеш приложения (партнёр по репликам работает без интернета).
const CACHE = 'repetitor-v4';
const ASSETS = [
  './', './index.html', './data/play.json', './audio/index.json', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png', './icons/icon-180.png'
];
// mp3-реплики кешируются на лету при первом проигрывании сцены (network-first ниже),
// поэтому прогнав сцену дома с интернетом, в машине услышишь её офлайн.

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  const isAudio = new URL(e.request.url).pathname.endsWith('.mp3');

  if (isAudio) {
    // тяжёлые реплики: cache-first (не перекачивать; офлайн в машине)
    e.respondWith(
      caches.match(e.request).then(r => r || fetch(e.request).then(resp => {
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
        return resp;
      }))
    );
  } else {
    // приложение и данные: сеть в обход HTTP-кеша (всегда свежее), откат в кеш офлайн
    e.respondWith(
      fetch(e.request, { cache: 'reload' }).then(resp => {
        const copy = resp.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
        return resp;
      }).catch(() => caches.match(e.request).then(r => r || caches.match('./index.html')))
    );
  }
});
