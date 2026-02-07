// 로컬스토리지 관리 모듈
class StorageManager {
  constructor() {
    this.KEYS = {
      FAVORITES: 'metropy_favorites',
      HISTORY: 'metropy_history',
      PREFERENCES: 'metropy_preferences',
      STATISTICS: 'metropy_statistics'
    };
    this.MAX_HISTORY = 10;
    this.QUOTA_WARN_KB = 4000; // 4MB — warn at ~80% of 5MB limit
  }

  // ==================== Safe JSON helpers ====================

  _safeGet(key, fallback = null) {
    try {
      const data = localStorage.getItem(key);
      return data ? JSON.parse(data) : fallback;
    } catch (e) {
      console.warn('[Storage] Corrupted data for key:', key, e);
      localStorage.removeItem(key);
      return fallback;
    }
  }

  _safeSet(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (e) {
      // QuotaExceededError — try evicting old data
      if (e.name === 'QuotaExceededError' || e.code === 22) {
        console.warn('[Storage] Quota exceeded, evicting old data...');
        this._evictOldData();
        try {
          localStorage.setItem(key, JSON.stringify(value));
          return true;
        } catch (e2) {
          console.error('[Storage] Still over quota after eviction:', e2);
          if (typeof window.showWarning === 'function') {
            window.showWarning('저장 공간이 부족합니다. 일부 오래된 데이터가 삭제됩니다.');
          }
          return false;
        }
      }
      console.error('[Storage] Failed to save:', e);
      return false;
    }
  }

  _evictOldData() {
    // 1. Trim history to 5 (from 10)
    const history = this._safeGet(this.KEYS.HISTORY, []);
    if (history.length > 5) {
      this._safeSet(this.KEYS.HISTORY, history.slice(0, 5));
    }
    // 2. Clear error log
    localStorage.removeItem('metropy_error_log');
    // 3. If still over, clear statistics
    const sizeKB = parseFloat(this.getStorageSize());
    if (sizeKB > this.QUOTA_WARN_KB) {
      this.resetStatistics();
    }
  }

  // ==================== 즐겨찾기 ====================

  getFavorites() {
    return this._safeGet(this.KEYS.FAVORITES, []);
  }

  addFavorite(route) {
    const favorites = this.getFavorites();
    const newFavorite = {
      id: Date.now(),
      name: route.name || `${route.boarding} → ${route.destination}`,
      boarding: route.boarding,
      destination: route.destination,
      hour: route.hour || 8,
      createdAt: new Date().toISOString()
    };

    // 중복 체크
    const exists = favorites.some(f =>
      f.boarding === newFavorite.boarding &&
      f.destination === newFavorite.destination
    );

    if (!exists) {
      favorites.unshift(newFavorite);
      return this._safeSet(this.KEYS.FAVORITES, favorites);
    }
    return false;
  }

  removeFavorite(id) {
    const favorites = this.getFavorites();
    const filtered = favorites.filter(f => f.id !== id);
    this._safeSet(this.KEYS.FAVORITES, filtered);
  }

  updateFavoriteName(id, newName) {
    const favorites = this.getFavorites();
    const favorite = favorites.find(f => f.id === id);
    if (favorite) {
      favorite.name = newName;
      this._safeSet(this.KEYS.FAVORITES, favorites);
    }
  }

  isFavorite(boarding, destination) {
    const favorites = this.getFavorites();
    return favorites.some(f =>
      f.boarding === boarding && f.destination === destination
    );
  }

  // ==================== 히스토리 ====================

  getHistory() {
    return this._safeGet(this.KEYS.HISTORY, []);
  }

  addHistory(route) {
    let history = this.getHistory();

    const newEntry = {
      boarding: route.boarding,
      destination: route.destination,
      hour: route.hour,
      direction: route.direction,
      timestamp: new Date().toISOString()
    };

    // 중복 제거 (같은 경로는 최신 것만)
    history = history.filter(h =>
      !(h.boarding === newEntry.boarding && h.destination === newEntry.destination)
    );

    history.unshift(newEntry);

    // 최대 개수 제한
    if (history.length > this.MAX_HISTORY) {
      history = history.slice(0, this.MAX_HISTORY);
    }

    this._safeSet(this.KEYS.HISTORY, history);
  }

  clearHistory() {
    this._safeSet(this.KEYS.HISTORY, []);
  }

  // ==================== 사용자 설정 ====================

  getPreferences() {
    return this._safeGet(this.KEYS.PREFERENCES, this.getDefaultPreferences());
  }

  getDefaultPreferences() {
    return {
      theme: 'dark',  // 'dark' or 'light'
      showHints: true,
      autoSaveHistory: true,
      notifications: false,
      vibration: true
    };
  }

  setPreference(key, value) {
    const prefs = this.getPreferences();
    prefs[key] = value;
    this._safeSet(this.KEYS.PREFERENCES, prefs);
  }

  setPreferences(prefs) {
    this._safeSet(this.KEYS.PREFERENCES, prefs);
  }

  // ==================== 통계 ====================

  getStatistics() {
    return this._safeGet(this.KEYS.STATISTICS, this.getDefaultStatistics());
  }

  getDefaultStatistics() {
    return {
      totalRecommendations: 0,
      firstUsed: new Date().toISOString(),
      lastUsed: new Date().toISOString(),
      mostUsedRoute: null,
      carPreferences: {},  // { 1: 5, 2: 3, ... } 칸별 선택 횟수
      routeCount: {}  // 경로별 사용 횟수
    };
  }

  incrementRecommendation(route, bestCar) {
    const stats = this.getStatistics();

    stats.totalRecommendations++;
    stats.lastUsed = new Date().toISOString();

    // 칸 선호도 업데이트
    stats.carPreferences[bestCar] = (stats.carPreferences[bestCar] || 0) + 1;

    // 경로 사용 횟수
    const routeKey = `${route.boarding}→${route.destination}`;
    stats.routeCount[routeKey] = (stats.routeCount[routeKey] || 0) + 1;

    // 가장 많이 사용한 경로
    const maxRoute = Object.entries(stats.routeCount)
      .sort((a, b) => b[1] - a[1])[0];
    if (maxRoute) {
      stats.mostUsedRoute = { route: maxRoute[0], count: maxRoute[1] };
    }

    this._safeSet(this.KEYS.STATISTICS, stats);
  }

  resetStatistics() {
    this._safeSet(this.KEYS.STATISTICS, this.getDefaultStatistics());
  }

  // ==================== 전체 데이터 관리 ====================

  exportData() {
    return {
      favorites: this.getFavorites(),
      history: this.getHistory(),
      preferences: this.getPreferences(),
      statistics: this.getStatistics(),
      exportDate: new Date().toISOString()
    };
  }

  importData(data) {
    if (data.favorites) {
      this._safeSet(this.KEYS.FAVORITES, data.favorites);
    }
    if (data.history) {
      this._safeSet(this.KEYS.HISTORY, data.history);
    }
    if (data.preferences) {
      this._safeSet(this.KEYS.PREFERENCES, data.preferences);
    }
    if (data.statistics) {
      this._safeSet(this.KEYS.STATISTICS, data.statistics);
    }
  }

  clearAllData() {
    Object.values(this.KEYS).forEach(key => {
      localStorage.removeItem(key);
    });
  }

  getStorageSize() {
    let total = 0;
    for (let key in localStorage) {
      if (localStorage.hasOwnProperty(key)) {
        total += localStorage[key].length + key.length;
      }
    }
    return (total / 1024).toFixed(2); // KB
  }
}

// 전역 인스턴스
const storage = new StorageManager();
