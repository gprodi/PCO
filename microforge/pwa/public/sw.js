// Service worker MicroForge : l'interface reste disponible hors ligne ; les API restent en ligne
// (données personnelles jamais mises en cache).
const CACHE = 'microforge-dev'; // remplacé à la construction par un nom propre à la version
const BUILD_ASSETS = []; // remplacé à la construction par la liste des fichiers produits
const SHELL = ['./', './index.html', './manifest.webmanifest', './icon.svg', ...BUILD_ASSETS];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))),
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  // Autre origine (api_data, api_ia) ou écriture : réseau uniquement.
  if (event.request.method !== 'GET' || url.origin !== self.location.origin) return;
  // Atelier virtuel (cadre isolé, sa propre CSP) : toujours le réseau, jamais la page de l'application.
  if (url.pathname.includes('/atelier/')) return;
  // config.js : réseau d'abord (une nouvelle configuration ne reste pas coincée en cache).
  if (url.pathname.endsWith('/config.js')) {
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request, { ignoreVary: true })),
    );
    return;
  }
  // ignoreVary : les requêtes de modules portent un en-tête Origin absent du préchargement.
  event.respondWith(
    caches.match(event.request, { ignoreVary: true }).then(
      (hit) =>
        hit ||
        fetch(event.request)
          .then((res) => {
            if (res.ok) {
              const copy = res.clone();
              caches.open(CACHE).then((cache) => cache.put(event.request, copy));
            }
            return res;
          })
          // Hors ligne : la page d'accueil pour une navigation, une erreur réseau pour le reste.
          .catch(() => (event.request.mode === 'navigate' ? caches.match('./index.html') : Response.error())),
    ),
  );
});
