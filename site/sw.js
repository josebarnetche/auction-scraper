/**
 * Subasto.com.ar - Service Worker
 *
 * Provides offline support, caching, background sync,
 * and push notifications for the PWA.
 *
 * Cache Strategy:
 * - Static assets: Cache First (long-term)
 * - API responses: Network First with cache fallback
 * - Images: Cache First with network fallback
 * - HTML: Network First (for freshness)
 */

const CACHE_VERSION = 'v1.6.0';
const STATIC_CACHE = `subasto-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `subasto-dynamic-${CACHE_VERSION}`;
const API_CACHE = `subasto-api-${CACHE_VERSION}`;
const IMAGE_CACHE = `subasto-images-${CACHE_VERSION}`;

// Assets to pre-cache on install
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/offline.html',
    '/manifest.json',
    '/favicon.svg',
    '/favicon-16x16.png',
    '/favicon-32x32.png',
    '/apple-touch-icon.png',
    '/api/placeholder.svg',
    '/js/alerts.js',
    '/js/pwa.js'
];

// External assets to cache
const EXTERNAL_ASSETS = [
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js',
    'https://cdn.jsdelivr.net/gh/studio-freight/lenis@1.0.29/bundled/lenis.min.js',
    'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Manrope:wght@300;400;500;600;700&display=swap'
];

// API endpoints to cache
const API_ENDPOINTS = [
    '/api/listings.json'
];

// Cache expiration times (in seconds)
const CACHE_EXPIRATION = {
    api: 5 * 60,        // 5 minutes for API
    images: 7 * 24 * 60 * 60,  // 7 days for images
    static: 30 * 24 * 60 * 60   // 30 days for static assets
};

// ============================================
// INSTALL EVENT
// ============================================
self.addEventListener('install', (event) => {
    console.log('[SW] Installing Service Worker...');

    event.waitUntil(
        Promise.all([
            // Cache static assets
            caches.open(STATIC_CACHE).then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            }),
            // Cache external assets (best effort)
            caches.open(STATIC_CACHE).then((cache) => {
                return Promise.allSettled(
                    EXTERNAL_ASSETS.map(url =>
                        cache.add(url).catch(err => {
                            console.log('[SW] Could not cache:', url);
                        })
                    )
                );
            })
        ]).then(() => {
            console.log('[SW] Installation complete');
            return self.skipWaiting();
        })
    );
});

// ============================================
// ACTIVATE EVENT
// ============================================
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating Service Worker...');

    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames
                    .filter((cacheName) => {
                        return cacheName.startsWith('subasto-') &&
                               !cacheName.includes(CACHE_VERSION);
                    })
                    .map((cacheName) => {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    })
            );
        }).then(() => {
            console.log('[SW] Activation complete');
            return self.clients.claim();
        })
    );
});

// ============================================
// FETCH EVENT
// ============================================
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') {
        return;
    }

    // Skip Chrome extension requests
    if (url.protocol === 'chrome-extension:') {
        return;
    }

    // API requests - Network First
    if (isApiRequest(url)) {
        event.respondWith(networkFirstStrategy(request, API_CACHE, CACHE_EXPIRATION.api));
        return;
    }

    // Image requests - Cache First
    if (isImageRequest(url)) {
        event.respondWith(cacheFirstStrategy(request, IMAGE_CACHE));
        return;
    }

    // HTML requests - Network First
    if (request.headers.get('accept')?.includes('text/html')) {
        event.respondWith(networkFirstWithOffline(request));
        return;
    }

    // Static assets - Cache First
    if (isStaticAsset(url)) {
        event.respondWith(cacheFirstStrategy(request, STATIC_CACHE));
        return;
    }

    // Default - Network First
    event.respondWith(networkFirstStrategy(request, DYNAMIC_CACHE));
});

// ============================================
// CACHING STRATEGIES
// ============================================

/**
 * Cache First Strategy
 * Try cache first, then network, cache the response
 */
async function cacheFirstStrategy(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cachedResponse = await cache.match(request);

    if (cachedResponse) {
        // Update cache in background
        refreshCache(request, cache);
        return cachedResponse;
    }

    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.log('[SW] Cache First failed:', request.url);
        return new Response('Resource not available', { status: 503 });
    }
}

/**
 * Network First Strategy
 * Try network first, fallback to cache
 */
async function networkFirstStrategy(request, cacheName, maxAge = 300) {
    const cache = await caches.open(cacheName);

    try {
        const networkResponse = await fetch(request);

        if (networkResponse.ok) {
            // Add timestamp to cached response
            const responseClone = networkResponse.clone();
            const headers = new Headers(responseClone.headers);
            headers.append('sw-cached-at', Date.now().toString());

            const body = await responseClone.blob();
            const cachedResponse = new Response(body, {
                status: responseClone.status,
                statusText: responseClone.statusText,
                headers: headers
            });

            cache.put(request, cachedResponse);
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Network failed, trying cache:', request.url);

        const cachedResponse = await cache.match(request);

        if (cachedResponse) {
            // Check if cache is expired
            const cachedAt = cachedResponse.headers.get('sw-cached-at');
            if (cachedAt) {
                const age = (Date.now() - parseInt(cachedAt)) / 1000;
                if (age > maxAge * 10) { // Allow 10x max age for offline
                    console.log('[SW] Cache too old:', request.url);
                }
            }
            return cachedResponse;
        }

        return new Response(JSON.stringify({
            error: 'offline',
            message: 'No hay conexion a internet',
            cached: false
        }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

/**
 * Network First with Offline Fallback for HTML
 */
async function networkFirstWithOffline(request) {
    try {
        const networkResponse = await fetch(request);

        if (networkResponse.ok) {
            const cache = await caches.open(STATIC_CACHE);
            cache.put(request, networkResponse.clone());
        }

        return networkResponse;
    } catch (error) {
        console.log('[SW] Offline, serving cached HTML or offline page');

        // Try to serve cached version
        const cache = await caches.open(STATIC_CACHE);
        const cachedResponse = await cache.match(request);

        if (cachedResponse) {
            return cachedResponse;
        }

        // Serve offline page
        const offlineResponse = await cache.match('/offline.html');
        if (offlineResponse) {
            return offlineResponse;
        }

        return new Response('Offline', { status: 503 });
    }
}

/**
 * Refresh cache in background (stale-while-revalidate)
 */
async function refreshCache(request, cache) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            cache.put(request, networkResponse.clone());
        }
    } catch (error) {
        // Silently fail - we have cached version
    }
}

// ============================================
// HELPER FUNCTIONS
// ============================================

function isApiRequest(url) {
    return url.pathname.startsWith('/api/') && url.pathname.endsWith('.json');
}

function isImageRequest(url) {
    const imageExtensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico'];
    return imageExtensions.some(ext => url.pathname.toLowerCase().endsWith(ext)) ||
           url.pathname.includes('/images/') ||
           url.hostname.includes('cloudinary') ||
           url.hostname.includes('imgur');
}

function isStaticAsset(url) {
    const staticExtensions = ['.js', '.css', '.woff', '.woff2', '.ttf', '.eot'];
    return staticExtensions.some(ext => url.pathname.toLowerCase().endsWith(ext));
}

// ============================================
// PUSH NOTIFICATIONS
// ============================================
self.addEventListener('push', (event) => {
    console.log('[SW] Push received:', event);

    let data = {
        title: 'Subasto.com.ar',
        body: 'Nueva actualizacion disponible',
        icon: '/favicon-32x32.png',
        badge: '/favicon-16x16.png',
        tag: 'subasto-notification',
        data: {}
    };

    if (event.data) {
        try {
            const pushData = event.data.json();
            data = { ...data, ...pushData };
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: data.icon || '/favicon-32x32.png',
        badge: data.badge || '/favicon-16x16.png',
        tag: data.tag || 'subasto-notification',
        data: data.data || {},
        vibrate: [200, 100, 200],
        requireInteraction: data.urgent || false,
        actions: data.actions || [
            { action: 'view', title: 'Ver' },
            { action: 'dismiss', title: 'Cerrar' }
        ]
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked:', event);

    event.notification.close();

    const action = event.action;
    const data = event.notification.data || {};

    if (action === 'dismiss') {
        return;
    }

    // Default action: open the app
    let urlToOpen = data.url || '/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((windowClients) => {
                // Check if app is already open
                for (const client of windowClients) {
                    if (client.url.includes('subasto') && 'focus' in client) {
                        client.postMessage({
                            type: 'notification-click',
                            data: data
                        });
                        return client.focus();
                    }
                }
                // Open new window
                return clients.openWindow(urlToOpen);
            })
    );
});

// ============================================
// BACKGROUND SYNC
// ============================================
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);

    if (event.tag === 'sync-watchlist') {
        event.waitUntil(syncWatchlist());
    }

    if (event.tag === 'sync-searches') {
        event.waitUntil(syncSavedSearches());
    }
});

async function syncWatchlist() {
    console.log('[SW] Syncing watchlist...');

    try {
        // Get watchlist from IndexedDB or send message to client
        const clients = await self.clients.matchAll();

        for (const client of clients) {
            client.postMessage({
                type: 'sync-watchlist',
                timestamp: Date.now()
            });
        }

        return true;
    } catch (error) {
        console.error('[SW] Watchlist sync failed:', error);
        throw error;
    }
}

async function syncSavedSearches() {
    console.log('[SW] Syncing saved searches...');

    try {
        // Fetch fresh API data
        const response = await fetch('/api/listings.json');
        if (response.ok) {
            const cache = await caches.open(API_CACHE);
            await cache.put('/api/listings.json', response.clone());

            // Notify clients
            const clients = await self.clients.matchAll();
            for (const client of clients) {
                client.postMessage({
                    type: 'data-updated',
                    timestamp: Date.now()
                });
            }
        }

        return true;
    } catch (error) {
        console.error('[SW] Saved searches sync failed:', error);
        throw error;
    }
}

// ============================================
// PERIODIC SYNC (if supported)
// ============================================
self.addEventListener('periodicsync', (event) => {
    console.log('[SW] Periodic sync:', event.tag);

    if (event.tag === 'update-auctions') {
        event.waitUntil(updateAuctionData());
    }
});

async function updateAuctionData() {
    try {
        const response = await fetch('/api/listings.json');
        if (response.ok) {
            const cache = await caches.open(API_CACHE);
            await cache.put('/api/listings.json', response);

            const data = await response.clone().json();

            // Check for ending auctions and notify
            await checkEndingAuctions(data.listings || []);
        }
    } catch (error) {
        console.error('[SW] Periodic update failed:', error);
    }
}

async function checkEndingAuctions(listings) {
    // This would check watched auctions and send notifications
    // Implementation would require IndexedDB for storing watched items
    console.log('[SW] Checking ending auctions...');
}

// ============================================
// MESSAGE HANDLER
// ============================================
self.addEventListener('message', (event) => {
    console.log('[SW] Message received:', event.data);

    const { type, payload } = event.data || {};

    switch (type) {
        case 'skip-waiting':
            self.skipWaiting();
            break;

        case 'cache-urls':
            if (payload?.urls) {
                caches.open(DYNAMIC_CACHE).then(cache => {
                    cache.addAll(payload.urls);
                });
            }
            break;

        case 'clear-cache':
            clearAllCaches();
            break;

        case 'get-cache-status':
            getCacheStatus().then(status => {
                event.source.postMessage({
                    type: 'cache-status',
                    payload: status
                });
            });
            break;
    }
});

async function clearAllCaches() {
    const cacheNames = await caches.keys();
    await Promise.all(
        cacheNames.map(name => caches.delete(name))
    );
    console.log('[SW] All caches cleared');
}

async function getCacheStatus() {
    const cacheNames = await caches.keys();
    const status = {};

    for (const name of cacheNames) {
        const cache = await caches.open(name);
        const keys = await cache.keys();
        status[name] = keys.length;
    }

    return status;
}

console.log('[SW] Service Worker loaded - version:', CACHE_VERSION);
