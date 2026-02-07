// PWA Service Worker
const CACHE_NAME = 'metropy-v2.1.0';
const urlsToCache = [
  '/',
  '/static/css/style.css',
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
  '/static/js/app.js',
  '/static/favicon.svg',
  '/static/manifest.json',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.js',
  'https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;600;700;800;900&display=swap'
];

// 설치
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
  self.skipWaiting();
});

// 활성화
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME) {
            console.log('Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch - Network First, fallback to Cache
self.addEventListener('fetch', (event) => {
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // API 요청은 캐시하지 않음
        if (event.request.url.includes('/api/') || event.request.url.includes('/health')) {
          return response;
        }

        // 성공적인 응답을 캐시에 저장
        const responseToCache = response.clone();
        caches.open(CACHE_NAME)
          .then((cache) => {
            cache.put(event.request, responseToCache);
          });

        return response;
      })
      .catch(() => {
        // 네트워크 실패 시 캐시에서 반환
        return caches.match(event.request);
      })
  );
});

// Background Sync (나중에 구현)
// self.addEventListener('sync', (event) => {
//   if (event.tag === 'sync-recommendations') {
//     event.waitUntil(syncRecommendations());
//   }
// });
