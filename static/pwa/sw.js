/**
 * InvestZA Service Worker
 * Strategy:
 *   - Static assets (CSS/JS/fonts/icons): Cache-first with background update
 *   - HTML pages (dashboard, deposits, etc.): Network-first, fall back to cache
 *   - API/POST requests: Network-only (never cache financial data)
 *   - Offline fallback page for when network fails and no cache exists
 */

const CACHE_VERSION = 'iz-v1';
const STATIC_CACHE  = `${CACHE_VERSION}-static`;
const PAGE_CACHE    = `${CACHE_VERSION}-pages`;

// Static assets to pre-cache on install
const PRECACHE_ASSETS = [
  '/static/pwa/manifest.json',
  '/static/icons/icon-192.svg',
  '/static/icons/icon-512.svg',
  // Google Fonts are cached on first fetch via the dynamic handler
];

// Routes that are always network-only (financial / auth mutations)
const NETWORK_ONLY_PATTERNS = [
  /\/deposits\/(bank|crypto)\/create/,
  /\/withdrawals\//,
  /\/accounts\/(login|logout|register|password)/,
  /\/platform-admin\//,
  /\/admin-panel\//,
  /\/api\//,
];

// ── Install ──────────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(PRECACHE_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: clean up old caches ────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k.startsWith('iz-') && k !== STATIC_CACHE && k !== PAGE_CACHE)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch ────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // 1. Only handle same-origin + Google Fonts
  const isGoogleFonts = url.hostname.includes('fonts.g');
  if (!isGoogleFonts && url.origin !== self.location.origin) return;

  // 2. Never cache POST / mutations or sensitive routes
  if (request.method !== 'GET') return;
  if (NETWORK_ONLY_PATTERNS.some(p => p.test(url.pathname))) return;

  // 3. Static assets → Cache-first, refresh in background
  const isStatic = (
    url.pathname.startsWith('/static/') ||
    isGoogleFonts ||
    /\.(woff2?|ttf|otf|eot)$/.test(url.pathname)
  );

  if (isStatic) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // 4. HTML pages → Network-first, cache on success, offline fallback
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirst(request, PAGE_CACHE));
    return;
  }

  // 5. Everything else → network only
});

// ── Strategies ───────────────────────────────────────────────────────────────
async function cacheFirst(request, cacheName) {
  const cache    = await caches.open(cacheName);
  const cached   = await cache.match(request);
  if (cached) {
    // Refresh in background (stale-while-revalidate)
    fetch(request).then(res => { if (res.ok) cache.put(request, res.clone()); }).catch(() => {});
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    return new Response('Offline', { status: 503 });
  }
}

async function networkFirst(request, cacheName) {
  const cache = await caches.open(cacheName);
  try {
    const response = await fetch(request);
    if (response.ok) cache.put(request, response.clone());
    return response;
  } catch {
    const cached = await cache.match(request);
    if (cached) return cached;
    // Return the offline page if cached, else minimal HTML
    const offline = await cache.match('/offline/');
    return offline || new Response(offlineFallback(), {
      headers: { 'Content-Type': 'text/html' }
    });
  }
}

// ── Minimal offline fallback HTML ────────────────────────────────────────────
function offlineFallback() {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>You're Offline — InvestZA</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:'DM Sans',system-ui,sans-serif;background:#eff3fa;color:#0a1f44;
       display:flex;align-items:center;justify-content:center;min-height:100vh;padding:24px;}
  .card{background:#fff;border-radius:16px;padding:40px 32px;max-width:420px;width:100%;
        text-align:center;box-shadow:0 8px 32px rgba(10,31,68,0.1);}
  svg{margin:0 auto 20px;display:block;}
  h1{font-family:Georgia,serif;font-size:1.5rem;margin-bottom:8px;}
  p{color:#64748b;font-size:0.9rem;line-height:1.6;margin-bottom:24px;}
  a{display:inline-block;padding:10px 28px;background:#e08900;color:#fff;
    border-radius:99px;font-weight:600;font-size:0.875rem;text-decoration:none;}
</style>
</head>
<body>
<div class="card">
  <svg width="64" height="74" viewBox="0 0 80 92" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M40 4 L74 16 L74 46 C74 64 58 78 40 88 C22 78 6 64 6 46 L6 16 Z"
          stroke="#f5980a" stroke-width="3" fill="rgba(245,152,10,0.08)"/>
    <path d="M27 46 L36 55 L54 36" stroke="#f5980a" stroke-width="4"
          stroke-linecap="round" stroke-linejoin="round"/>
  </svg>
  <h1>You're Offline</h1>
  <p>It looks like you've lost your internet connection. Your InvestZA data is safe — reconnect to continue.</p>
  <a href="/" onclick="location.reload();return false;">Try Again</a>
</div>
</body>
</html>`;
}
