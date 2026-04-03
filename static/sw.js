/**
 * sw.js — MediTrack Service Worker
 * Caches static assets and pages for offline use
 */
const CACHE_NAME = 'meditrack-v1';
const STATIC_ASSETS = [
    '/static/js/voice.js',
    '/static/js/search.js',
    '/static/js/upload.js',
    '/static/js/offline.js',
    '/static/js/shortcuts.js',
    'https://cdn.tailwindcss.com',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap',
];

// Install: cache static assets
self.addEventListener('install', event => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return Promise.allSettled(STATIC_ASSETS.map(url => cache.add(url).catch(() => null)));
        })
    );
});

// Activate: clean old caches
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

// Fetch: serve from cache when offline, network-first for API calls
self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // Don't intercept POST/API mutation requests
    if (event.request.method !== 'GET') return;

    // Network-first for dynamic pages
    if (url.pathname.startsWith('/search-patients/') ||
        url.pathname.startsWith('/sync-offline-visit/') ||
        url.pathname.startsWith('/django-admin/')) {
        return;
    }

    // Stale-while-revalidate for static assets
    if (url.pathname.startsWith('/static/') ||
        url.origin === 'https://cdn.tailwindcss.com' ||
        url.origin === 'https://fonts.googleapis.com' ||
        url.origin === 'https://fonts.gstatic.com') {
        event.respondWith(
            caches.match(event.request).then(cached => {
                const fetchPromise = fetch(event.request).then(resp => {
                    if (resp && resp.status === 200) {
                        caches.open(CACHE_NAME).then(c => c.put(event.request, resp.clone()));
                    }
                    return resp;
                }).catch(() => null);
                return cached || fetchPromise;
            })
        );
        return;
    }

    // Network-first for all other pages, fallback to cache
    event.respondWith(
        fetch(event.request)
            .then(resp => {
                if (resp && resp.status === 200 && resp.type !== 'opaque') {
                    const clone = resp.clone();
                    caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
                }
                return resp;
            })
            .catch(() => caches.match(event.request))
    );
});
