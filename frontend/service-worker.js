// PWA Service Worker
// IMPORTANT: Increment CACHE_VERSION on EVERY deploy to bust the cache
const CACHE_VERSION = 'v7';  // <-- Change this when deploying new code
const CACHE_NAME = `metropy-cache-${CACHE_VERSION}`;
const API_CACHE_NAME = 'metropy-api-v1';
const API_CACHE_TTL = 5 * 60 * 1000; // 5 minutes
const STATIC_ASSETS = [
  '/',
  '/static/css/variables.css',
  '/static/css/base.css',
  '/static/css/layout.css',
  '/static/css/components.css',
  '/static/css/results.css',
  '/static/css/responsive.css',
  '/static/js/error-handler.js',
  '/static/js/storage.js',
  '/static/js/api.js',
  '/static/js/car-viz.js',
  '/static/js/touch.js',
  '/static/js/favorites.js',
  '/static/js/keyboard.js',
  '/static/js/search.js',
  '/static/js/explanation.js',
  '/static/js/geolocation.js',
  '/static/js/feedback.js',
  '/static/js/compare.js',
  '/static/js/metro-map-image.js',
  '/static/js/app.js',
  '/static/js/stats-pwa.js',
  '/static/img/naver_subway_line2.png',
  '/static/favicon.svg',
  '/static/manifest.json',
];

const CDN_ASSETS = [
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js',
  'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap'
];

// 설치 — 정적 자산만 먼저 캐시, CDN은 별도 처리
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(async (cache) => {
        // 정적 자산 먼저 캐시 (실패하면 설치 실패)
        await cache.addAll(STATIC_ASSETS);
        // CDN 자산은 실패해도 설치 진행 (optional)
        await Promise.allSettled(
          CDN_ASSETS.map(url => cache.add(url).catch(() => {
            console.warn('CDN 캐시 실패 (건너뜀):', url);
          }))
        );
      })
  );
  self.skipWaiting();
});

// 활성화 — 이전 캐시 정리 + SW 업데이트 알림
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName !== API_CACHE_NAME) {
            console.log('이전 캐시 삭제:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
      // Notify all clients that a new version is active
      self.clients.matchAll().then(clients => {
        clients.forEach(client => {
          client.postMessage({ type: 'SW_UPDATED', version: CACHE_NAME });
        });
      });
    })
  );
  self.clients.claim();
});

// Fetch 전략:
// - 정적 자산: Stale-While-Revalidate (빠른 로딩 + 백그라운드 업데이트)
// - API 요청: Network-only (캐시 안 함)
// - Navigation: Network-first, 오프라인 시 캐시된 메인 페이지 반환
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // API /recommend — Stale-While-Revalidate (5분 TTL)
  // 캐시된 결과 즉시 반환 + 백그라운드에서 최신 데이터 fetch
  if (url.pathname === '/api/recommend' && request.method === 'POST') {
    event.respondWith(
      (async () => {
        const cache = await caches.open(API_CACHE_NAME);
        // POST body를 캐시 키로 사용
        const body = await request.clone().text();
        const cacheKey = new Request(`/api/recommend?_body=${encodeURIComponent(body)}`);

        const cached = await cache.match(cacheKey);
        const cachedTime = cached ? parseInt(cached.headers.get('x-cached-at') || '0') : 0;
        const isStale = Date.now() - cachedTime > API_CACHE_TTL;

        // 백그라운드에서 항상 새 데이터 fetch
        const networkPromise = fetch(request.clone())
          .then(async (networkResponse) => {
            if (networkResponse.ok) {
              const responseBody = await networkResponse.clone().text();
              const headers = new Headers(networkResponse.headers);
              headers.set('x-cached-at', String(Date.now()));
              const cachedResponse = new Response(responseBody, {
                status: networkResponse.status,
                statusText: networkResponse.statusText,
                headers
              });
              await cache.put(cacheKey, cachedResponse);
            }
            return networkResponse;
          })
          .catch(() => null);

        // 캐시가 있고 fresh하면 즉시 반환
        if (cached && !isStale) {
          return cached;
        }
        // 캐시가 stale이면 반환하되 백그라운드 업데이트 진행
        if (cached && isStale) {
          networkPromise; // fire-and-forget
          return cached;
        }
        // 캐시 없으면 네트워크 대기
        const networkResponse = await networkPromise;
        if (networkResponse) return networkResponse;
        return new Response(
          JSON.stringify({ detail: '오프라인 상태입니다. 인터넷 연결을 확인해주세요.' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      })()
    );
    return;
  }

  // 기타 API 요청 — 네트워크만 사용
  if (url.pathname.startsWith('/api/') || url.pathname === '/health') {
    event.respondWith(
      fetch(request).catch(() => {
        return new Response(
          JSON.stringify({ detail: '오프라인 상태입니다. 인터넷 연결을 확인해주세요.' }),
          { status: 503, headers: { 'Content-Type': 'application/json' } }
        );
      })
    );
    return;
  }

  // Navigation 요청 — Network-first, 오프라인 시 캐시된 메인 페이지
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
          return response;
        })
        .catch(() => caches.match('/') || caches.match(request))
    );
    return;
  }

  // 정적 자산 — Stale-While-Revalidate
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      const fetchPromise = fetch(request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const clone = networkResponse.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(request, clone));
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
