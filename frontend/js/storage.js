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
  }

  // ==================== 즐겨찾기 ====================

  getFavorites() {
    const data = localStorage.getItem(this.KEYS.FAVORITES);
    return data ? JSON.parse(data) : [];
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
      localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(favorites));
      return true;
    }
    return false;
  }

  removeFavorite(id) {
    const favorites = this.getFavorites();
    const filtered = favorites.filter(f => f.id !== id);
    localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(filtered));
  }

  updateFavoriteName(id, newName) {
    const favorites = this.getFavorites();
    const favorite = favorites.find(f => f.id === id);
    if (favorite) {
      favorite.name = newName;
      localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(favorites));
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
    const data = localStorage.getItem(this.KEYS.HISTORY);
    return data ? JSON.parse(data) : [];
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

    localStorage.setItem(this.KEYS.HISTORY, JSON.stringify(history));
  }

  clearHistory() {
    localStorage.setItem(this.KEYS.HISTORY, JSON.stringify([]));
  }

  // ==================== 사용자 설정 ====================

  getPreferences() {
    const data = localStorage.getItem(this.KEYS.PREFERENCES);
    return data ? JSON.parse(data) : this.getDefaultPreferences();
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
    localStorage.setItem(this.KEYS.PREFERENCES, JSON.stringify(prefs));
  }

  setPreferences(prefs) {
    localStorage.setItem(this.KEYS.PREFERENCES, JSON.stringify(prefs));
  }

  // ==================== 통계 ====================

  getStatistics() {
    const data = localStorage.getItem(this.KEYS.STATISTICS);
    return data ? JSON.parse(data) : this.getDefaultStatistics();
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

    localStorage.setItem(this.KEYS.STATISTICS, JSON.stringify(stats));
  }

  resetStatistics() {
    localStorage.setItem(this.KEYS.STATISTICS, JSON.stringify(this.getDefaultStatistics()));
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
      localStorage.setItem(this.KEYS.FAVORITES, JSON.stringify(data.favorites));
    }
    if (data.history) {
      localStorage.setItem(this.KEYS.HISTORY, JSON.stringify(data.history));
    }
    if (data.preferences) {
      localStorage.setItem(this.KEYS.PREFERENCES, JSON.stringify(data.preferences));
    }
    if (data.statistics) {
      localStorage.setItem(this.KEYS.STATISTICS, JSON.stringify(data.statistics));
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
