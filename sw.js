/* Service Worker — Farmácia Brasil (PWA offline) */
const CACHE = 'farmacia-v3';
const ASSETS = [
  './',
  'index.html',
  'medicamentos.json',
  'catalogo.json',
  'manifest.webmanifest',
  'icon.svg',
  'icon-192.png',
  'icon-512.png',
  'https://cdn.jsdelivr.net/npm/@zxing/library@0.21.3/umd/index.min.js'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE).then(c => Promise.allSettled(ASSETS.map(u => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Dados: rede primeiro (para pegar atualizações), cai para cache offline
  if (url.pathname.endsWith('medicamentos.json') || url.pathname.endsWith('catalogo.json')) {
    e.respondWith(
      fetch(req).then(r => {
        const cp = r.clone();
        caches.open(CACHE).then(c => c.put(req, cp));
        return r;
      }).catch(() => caches.match(req))
    );
    return;
  }

  // Ignora o canal SSE do servidor local
  if (url.pathname.endsWith('/events')) return;

  // App shell: cache primeiro, atualiza em segundo plano
  e.respondWith(
    caches.match(req).then(hit => {
      const net = fetch(req).then(r => {
        if (r && r.status === 200 && (url.origin === location.origin || url.href.includes('zxing'))) {
          const cp = r.clone();
          caches.open(CACHE).then(c => c.put(req, cp));
        }
        return r;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
