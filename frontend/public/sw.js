/**
 * Service Worker for Automation Services Platform PWA.
 *
 * WHAT: Handles offline capabilities, caching, and push notifications.
 *
 * WHY: Service workers enable:
 * 1. Offline functionality - app works without network
 * 2. Fast loading - cached assets load instantly
 * 3. Push notifications - real-time alerts even when app closed
 * 4. Background sync - queue actions when offline
 *
 * HOW: Implements cache-first strategy for static assets,
 * network-first for API calls, and handles push events.
 */

const CACHE_NAME = 'automation-platform-v1';
const STATIC_CACHE = 'automation-static-v1';
const API_CACHE = 'automation-api-v1';

/**
 * Static assets to cache on install.
 * These are essential for offline functionality.
 */
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/offline.html',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

/**
 * API routes to cache.
 * User data is cached for offline access.
 */
const CACHEABLE_API_ROUTES = [
  '/api/auth/me',
  '/api/projects',
  '/api/tickets',
];

/**
 * Install event - cache static assets.
 *
 * WHAT: Pre-caches essential assets for offline use.
 *
 * WHY: Ensures app shell loads instantly and works offline.
 */
self.addEventListener('install', (event) => {
  console.log('[ServiceWorker] Install');

  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[ServiceWorker] Caching static assets');
      return cache.addAll(STATIC_ASSETS).catch((error) => {
        // Don't fail install if some assets aren't available
        console.warn('[ServiceWorker] Some assets failed to cache:', error);
        return Promise.resolve();
      });
    })
  );

  // Skip waiting to activate immediately
  self.skipWaiting();
});

/**
 * Activate event - clean up old caches.
 *
 * WHAT: Removes outdated caches when new SW activates.
 *
 * WHY: Prevents storage bloat and ensures fresh content.
 */
self.addEventListener('activate', (event) => {
  console.log('[ServiceWorker] Activate');

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((cacheName) => {
            // Delete old versioned caches
            return (
              cacheName.startsWith('automation-') &&
              cacheName !== STATIC_CACHE &&
              cacheName !== API_CACHE
            );
          })
          .map((cacheName) => {
            console.log('[ServiceWorker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          })
      );
    })
  );

  // Take control of all clients immediately
  self.clients.claim();
});

/**
 * Fetch event - handle network requests.
 *
 * WHAT: Intercepts all fetch requests for caching strategy.
 *
 * WHY: Enables offline functionality and faster loading.
 *
 * HOW: Uses different strategies based on request type:
 * - Static assets: Cache-first
 * - API calls: Network-first with fallback
 * - Navigation: Network-first with offline page
 */
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip chrome-extension and other non-http(s) requests
  if (!url.protocol.startsWith('http')) {
    return;
  }

  // API requests - Network first, cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstWithCache(request, API_CACHE));
    return;
  }

  // Static assets - Cache first, network fallback
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirstWithNetwork(request, STATIC_CACHE));
    return;
  }

  // Navigation requests - Network first, offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstWithOffline(request));
    return;
  }

  // Default - Network first
  event.respondWith(networkFirst(request));
});

/**
 * Cache-first strategy.
 *
 * WHAT: Serves from cache, falls back to network.
 *
 * WHY: Fast loading for static assets that rarely change.
 */
async function cacheFirstWithNetwork(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);

  if (cachedResponse) {
    // Update cache in background
    fetchAndCache(request, cache);
    return cachedResponse;
  }

  return fetchAndCache(request, cache);
}

/**
 * Network-first strategy with cache fallback.
 *
 * WHAT: Tries network, falls back to cache.
 *
 * WHY: Fresh data when online, cached data offline.
 */
async function networkFirstWithCache(request, cacheName) {
  const cache = await caches.open(cacheName);

  try {
    const response = await fetch(request);

    // Cache successful responses
    if (response.ok) {
      cache.put(request, response.clone());
    }

    return response;
  } catch (error) {
    // Network failed, try cache
    const cachedResponse = await cache.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }

    // Return error response
    return new Response(
      JSON.stringify({ error: 'Offline', message: 'No cached data available' }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}

/**
 * Network-first with offline page fallback.
 *
 * WHAT: Tries network, shows offline page if unavailable.
 *
 * WHY: Graceful degradation for navigation requests.
 */
async function networkFirstWithOffline(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch (error) {
    // Try to return cached page
    const cache = await caches.open(STATIC_CACHE);
    const cachedResponse = await cache.match(request);

    if (cachedResponse) {
      return cachedResponse;
    }

    // Return offline page
    const offlinePage = await cache.match('/offline.html');
    if (offlinePage) {
      return offlinePage;
    }

    // Last resort - basic offline response
    return new Response(
      '<html><body><h1>Offline</h1><p>Please check your connection.</p></body></html>',
      {
        status: 503,
        headers: { 'Content-Type': 'text/html' },
      }
    );
  }
}

/**
 * Network-first strategy.
 *
 * WHAT: Always tries network first.
 *
 * WHY: Default for non-critical requests.
 */
async function networkFirst(request) {
  try {
    return await fetch(request);
  } catch (error) {
    return new Response('Network error', { status: 503 });
  }
}

/**
 * Fetch and cache helper.
 *
 * WHAT: Fetches resource and caches it.
 *
 * WHY: Reusable caching logic.
 */
async function fetchAndCache(request, cache) {
  try {
    const response = await fetch(request);

    if (response.ok) {
      cache.put(request, response.clone());
    }

    return response;
  } catch (error) {
    throw error;
  }
}

/**
 * Check if URL is a static asset.
 *
 * WHAT: Determines if request is for a static file.
 *
 * WHY: Different caching strategies for different content.
 */
function isStaticAsset(pathname) {
  return (
    pathname.endsWith('.js') ||
    pathname.endsWith('.css') ||
    pathname.endsWith('.png') ||
    pathname.endsWith('.jpg') ||
    pathname.endsWith('.jpeg') ||
    pathname.endsWith('.gif') ||
    pathname.endsWith('.svg') ||
    pathname.endsWith('.ico') ||
    pathname.endsWith('.woff') ||
    pathname.endsWith('.woff2') ||
    pathname.endsWith('.ttf') ||
    pathname.endsWith('.eot')
  );
}

// =============================================================================
// Push Notifications
// =============================================================================

/**
 * Push event - handle incoming push notifications.
 *
 * WHAT: Receives and displays push notifications.
 *
 * WHY: Real-time alerts for important events like:
 * - New tickets
 * - Proposal approvals
 * - Invoice payments
 * - SLA warnings
 */
self.addEventListener('push', (event) => {
  console.log('[ServiceWorker] Push received');

  let data = {
    title: 'Automation Platform',
    body: 'You have a new notification',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/badge-72x72.png',
    tag: 'default',
    data: {},
  };

  try {
    if (event.data) {
      data = { ...data, ...event.data.json() };
    }
  } catch (e) {
    console.error('[ServiceWorker] Error parsing push data:', e);
  }

  const options = {
    body: data.body,
    icon: data.icon,
    badge: data.badge,
    tag: data.tag,
    data: data.data,
    vibrate: [100, 50, 100],
    actions: data.actions || [],
    requireInteraction: data.requireInteraction || false,
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

/**
 * Notification click event - handle notification interactions.
 *
 * WHAT: Opens app/URL when notification is clicked.
 *
 * WHY: Direct navigation to relevant content.
 */
self.addEventListener('notificationclick', (event) => {
  console.log('[ServiceWorker] Notification clicked');

  event.notification.close();

  const notificationData = event.notification.data || {};
  let targetUrl = notificationData.url || '/';

  // Handle action buttons
  if (event.action) {
    switch (event.action) {
      case 'view':
        targetUrl = notificationData.viewUrl || targetUrl;
        break;
      case 'dismiss':
        return; // Just close notification
      default:
        break;
    }
  }

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      // If a window is already open, focus it
      for (const client of clientList) {
        if (client.url === targetUrl && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise open new window
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});

/**
 * Notification close event - track dismissals.
 *
 * WHAT: Logs when notifications are dismissed.
 *
 * WHY: Analytics on notification engagement.
 */
self.addEventListener('notificationclose', (event) => {
  console.log('[ServiceWorker] Notification closed:', event.notification.tag);
});

// =============================================================================
// Background Sync
// =============================================================================

/**
 * Sync event - handle background sync.
 *
 * WHAT: Retries failed requests when back online.
 *
 * WHY: Ensures actions complete even with spotty connectivity.
 */
self.addEventListener('sync', (event) => {
  console.log('[ServiceWorker] Sync event:', event.tag);

  if (event.tag === 'sync-offline-actions') {
    event.waitUntil(syncOfflineActions());
  }
});

/**
 * Sync offline actions.
 *
 * WHAT: Replays queued offline actions.
 *
 * WHY: Data consistency when connectivity is intermittent.
 */
async function syncOfflineActions() {
  try {
    // Get queued actions from IndexedDB
    const db = await openDatabase();
    const actions = await getQueuedActions(db);

    for (const action of actions) {
      try {
        const response = await fetch(action.url, {
          method: action.method,
          headers: action.headers,
          body: action.body,
        });

        if (response.ok) {
          await removeAction(db, action.id);
        }
      } catch (error) {
        console.error('[ServiceWorker] Sync action failed:', error);
      }
    }
  } catch (error) {
    console.error('[ServiceWorker] Sync failed:', error);
  }
}

/**
 * Open IndexedDB database.
 *
 * WHAT: Opens/creates the offline actions database.
 *
 * WHY: Persistent storage for offline queue.
 */
function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('OfflineActions', 1);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('actions')) {
        db.createObjectStore('actions', { keyPath: 'id', autoIncrement: true });
      }
    };
  });
}

/**
 * Get queued actions from IndexedDB.
 */
function getQueuedActions(db) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['actions'], 'readonly');
    const store = transaction.objectStore('actions');
    const request = store.getAll();

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

/**
 * Remove processed action from IndexedDB.
 */
function removeAction(db, id) {
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(['actions'], 'readwrite');
    const store = transaction.objectStore('actions');
    const request = store.delete(id);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve();
  });
}

// =============================================================================
// Message Handling
// =============================================================================

/**
 * Message event - handle messages from app.
 *
 * WHAT: Receives commands from the main app.
 *
 * WHY: Two-way communication for:
 * - Cache management
 * - Skip waiting
 * - Notification permissions
 */
self.addEventListener('message', (event) => {
  console.log('[ServiceWorker] Message received:', event.data);

  const { type, payload } = event.data || {};

  switch (type) {
    case 'SKIP_WAITING':
      self.skipWaiting();
      break;

    case 'CLEAR_CACHE':
      event.waitUntil(
        caches.keys().then((cacheNames) =>
          Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)))
        )
      );
      break;

    case 'CACHE_URLS':
      event.waitUntil(
        caches.open(STATIC_CACHE).then((cache) => cache.addAll(payload.urls || []))
      );
      break;

    default:
      console.log('[ServiceWorker] Unknown message type:', type);
  }
});

console.log('[ServiceWorker] Service worker loaded');
