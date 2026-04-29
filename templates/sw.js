const CACHE_NAME = '{{ CACHE_NAME|default:"clinic-cache-v1" }}';

const STATIC_ASSETS = [
    '/static/js/tailwind.js',
    '/static/css/flatpickr.min.css',
    '/static/js/voice.js',
    '/static/js/upload.js'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS).catch(err => {
            console.warn('Failed to cache some assets', err);
        }))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)));
        })
    );
    self.clients.claim();
});

self.addEventListener('fetch', event => {
    const req = event.request;
    if (req.method !== 'GET') return;

    const url = new URL(req.url);

    // NEVER cache API calls — always fetch fresh data from server
    if (url.pathname.startsWith('/search-patients/') ||
        url.pathname.startsWith('/api/') ||
        url.pathname.startsWith('/keep-alive/')) {
        event.respondWith(fetch(req));
        return;
    }

    // HTML / pages: Network First, fallback to offline UI if we had one
    if (req.headers.get('accept').includes('text/html')) {
        event.respondWith(
            fetch(req).catch(() => caches.match(req))
        );
        return;
    }

    // Static assets: Cache First, fallback to network
    event.respondWith(
        caches.match(req).then(cached => cached || fetch(req).then(res => {
            const resClone = res.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(req, resClone));
            return res;
        }))
    );
});
