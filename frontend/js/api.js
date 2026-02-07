// Metropy API 클라이언트 with Caching
const API = (function() {
  // 캐시 설정
  const CACHE_TTL = 5 * 60 * 1000; // 5분 TTL
  const cache = new Map();

  // 캐시 키 생성
  function cacheKey(type, params) {
    return `${type}:${JSON.stringify(params)}`;
  }

  // 캐시에서 가져오기
  function getFromCache(key) {
    const item = cache.get(key);
    if (!item) return null;

    if (Date.now() - item.timestamp > CACHE_TTL) {
      cache.delete(key);
      return null;
    }
    return item.data;
  }

  // 캐시에 저장
  function setCache(key, data) {
    cache.set(key, {
      data: data,
      timestamp: Date.now()
    });

    // 캐시 크기 제한 (최대 50개)
    if (cache.size > 50) {
      const firstKey = cache.keys().next().value;
      cache.delete(firstKey);
    }
  }

  // 캐시 무효화 (calibration 변경 시)
  function invalidateRecommendCache() {
    for (const key of cache.keys()) {
      if (key.startsWith('recommend:') || key.startsWith('sensitivity:')) {
        cache.delete(key);
      }
    }
    console.log('[API] Recommend/sensitivity cache invalidated');
  }

  return {
    // 역 목록 가져오기 (캐싱)
    async getStations() {
      const key = cacheKey('stations', {});
      const cached = getFromCache(key);
      if (cached) return cached;

      const res = await fetch('/api/stations');
      const data = await res.json();
      setCache(key, data);
      return data;
    },

    // 추천 (캐싱)
    async recommend(boarding, destination, hour, direction = null, dow = null) {
      const params = { boarding, destination, hour, direction, dow };
      const key = cacheKey('recommend', params);
      const cached = getFromCache(key);
      if (cached) {
        console.log('[API] Cache hit for recommend');
        return cached;
      }

      // 24→0, 25→1 매핑 (막차 시간대 슬라이더 값 → 실제 시각)
      const apiHour = hour >= 24 ? hour - 24 : hour;
      const body = { boarding, destination, hour: apiHour };
      if (direction) body.direction = direction;
      if (dow) body.dow = dow;

      const res = await fetch('/api/recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '요청 실패');
      }

      const data = await res.json();
      setCache(key, data);
      return data;
    },

    // 캘리브레이션 가져오기
    async getCalibration() {
      const res = await fetch('/api/calibrate');
      return res.json();
    },

    // 캘리브레이션 설정 (캐시 무효화)
    async setCalibration(params) {
      const res = await fetch('/api/calibrate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
      });

      // 파라미터 변경 시 추천 캐시 무효화
      invalidateRecommendCache();

      return res.json();
    },

    // 민감도 분석 (캐싱)
    async getSensitivity(boarding, destination, hour) {
      const params = { boarding, destination, hour };
      const key = cacheKey('sensitivity', params);
      const cached = getFromCache(key);
      if (cached) {
        console.log('[API] Cache hit for sensitivity');
        return cached;
      }

      const queryParams = new URLSearchParams({ boarding, destination, hour });
      const res = await fetch(`/api/sensitivity?${queryParams}`);
      const data = await res.json();
      setCache(key, data);
      return data;
    },

    // 추천 캐시 무효화 (외부에서 직접 호출 가능)
    invalidateRecommendCache() {
      invalidateRecommendCache();
    },

    // 캐시 통계
    getCacheStats() {
      return {
        size: cache.size,
        keys: Array.from(cache.keys())
      };
    },

    // 캐시 클리어
    clearCache() {
      cache.clear();
    }
  };
})();
