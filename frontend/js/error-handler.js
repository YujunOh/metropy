// 향상된 에러 처리 모듈
class ErrorHandler {
  constructor() {
    this.errorLog = [];
    this.maxLogSize = 50;
    this.retryAttempts = new Map();
    this.maxRetries = 3;
    this.online = navigator.onLine;

    this.initOnlineDetection();
    this.initGlobalErrorHandlers();
  }

  // 온라인/오프라인 감지
  initOnlineDetection() {
    window.addEventListener('online', () => {
      this.online = true;
      this.showSuccess('인터넷 연결이 복구되었습니다');
      this.hideOfflineWarning();
    });

    window.addEventListener('offline', () => {
      this.online = false;
      this.showOfflineWarning();
    });
  }

  // 전역 에러 핸들러
  initGlobalErrorHandlers() {
    // JavaScript 런타임 에러
    window.addEventListener('error', (event) => {
      console.error('JavaScript Error:', event.error);
      this.logError({
        type: 'runtime',
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        stack: event.error?.stack
      });

      // 사용자에게는 간단한 메시지만 표시
      if (!this.isDevelopment()) {
        this.showError('예상치 못한 오류가 발생했습니다. 페이지를 새로고침 해주세요.');
      }
    });

    // Promise rejection 에러
    window.addEventListener('unhandledrejection', (event) => {
      console.error('Unhandled Promise Rejection:', event.reason);
      this.logError({
        type: 'promise',
        message: event.reason?.message || String(event.reason),
        stack: event.reason?.stack
      });

      // API 에러는 이미 처리되었을 가능성이 높으므로 무시
      if (event.reason?.name !== 'APIError') {
        this.showError('요청 처리 중 오류가 발생했습니다');
      }
    });
  }

  // 에러 로깅
  logError(error) {
    const errorEntry = {
      timestamp: Date.now(),
      date: new Date().toISOString(),
      ...error,
      userAgent: navigator.userAgent,
      url: window.location.href
    };

    this.errorLog.push(errorEntry);

    // 최대 로그 크기 유지
    if (this.errorLog.length > this.maxLogSize) {
      this.errorLog.shift();
    }

    // LocalStorage에 저장 (선택사항)
    try {
      localStorage.setItem('metropy_error_log', JSON.stringify(this.errorLog.slice(-10)));
    } catch (e) {
      console.error('Failed to save error log:', e);
    }
  }

  // API 에러 처리
  async handleAPIError(error, context = {}) {
    const { endpoint, method = 'GET', retryable = true } = context;

    // 오프라인 에러
    if (!this.online) {
      return this.handleOfflineError(endpoint);
    }

    // HTTP 상태 코드별 처리
    if (error.status) {
      switch (error.status) {
        case 400:
          return this.handle400Error(error);
        case 404:
          return this.handle404Error(error);
        case 429:
          return this.handle429Error(error, context);
        case 500:
        case 502:
        case 503:
        case 504:
          return this.handle5xxError(error, context);
        default:
          return this.handleGenericError(error);
      }
    }

    // 네트워크 에러 (연결 실패)
    if (error.name === 'TypeError' || error.message.includes('Failed to fetch')) {
      return this.handleNetworkError(error, context);
    }

    // 기타 에러
    return this.handleGenericError(error);
  }

  // 400 Bad Request
  handle400Error(error) {
    const message = error.detail || '잘못된 요청입니다. 입력값을 확인해주세요.';
    this.showError(message);
    this.logError({
      type: 'api',
      status: 400,
      message: message,
      detail: error.detail
    });
    throw error;
  }

  // 404 Not Found
  handle404Error(error) {
    const message = '요청한 리소스를 찾을 수 없습니다';
    this.showError(message);
    this.logError({
      type: 'api',
      status: 404,
      message: message
    });
    throw error;
  }

  // 429 Too Many Requests
  async handle429Error(error, context) {
    const retryAfter = error.headers?.get('Retry-After') || 5;
    this.showWarning(`요청이 너무 많습니다. ${retryAfter}초 후 다시 시도합니다...`);

    await this.sleep(retryAfter * 1000);

    // 재시도
    if (context.retryCallback) {
      return await context.retryCallback();
    }

    throw error;
  }

  // 5xx Server Error
  async handle5xxError(error, context) {
    const { endpoint, retryable = true } = context;
    const retryKey = endpoint || 'default';
    const attempts = this.retryAttempts.get(retryKey) || 0;

    if (retryable && attempts < this.maxRetries) {
      // 재시도
      this.retryAttempts.set(retryKey, attempts + 1);
      const backoff = Math.min(1000 * Math.pow(2, attempts), 10000);

      this.showWarning(`서버 오류가 발생했습니다. ${backoff / 1000}초 후 재시도합니다... (${attempts + 1}/${this.maxRetries})`);

      await this.sleep(backoff);

      if (context.retryCallback) {
        try {
          const result = await context.retryCallback();
          this.retryAttempts.delete(retryKey);
          this.showSuccess('재시도 성공!');
          return result;
        } catch (retryError) {
          return this.handle5xxError(retryError, context);
        }
      }
    } else {
      // 재시도 횟수 초과
      this.retryAttempts.delete(retryKey);
      this.showError('서버에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해주세요.');
      this.logError({
        type: 'api',
        status: error.status,
        message: '서버 오류 (재시도 실패)',
        attempts: attempts
      });
    }

    throw error;
  }

  // 네트워크 에러
  async handleNetworkError(error, context) {
    const { retryable = true } = context;

    if (!this.online) {
      return this.handleOfflineError(context.endpoint);
    }

    if (retryable) {
      this.showWarning('네트워크 연결이 불안정합니다. 재시도 중...');

      await this.sleep(2000);

      if (context.retryCallback) {
        try {
          return await context.retryCallback();
        } catch (retryError) {
          this.showError('네트워크 연결에 실패했습니다. 인터넷 연결을 확인해주세요.');
        }
      }
    } else {
      this.showError('네트워크 연결에 실패했습니다');
    }

    this.logError({
      type: 'network',
      message: error.message
    });

    throw error;
  }

  // 오프라인 에러
  handleOfflineError(endpoint) {
    this.showOfflineWarning();
    this.logError({
      type: 'offline',
      message: 'Offline request attempted',
      endpoint: endpoint
    });

    const error = new Error('오프라인 상태입니다');
    error.offline = true;
    throw error;
  }

  // 일반 에러
  handleGenericError(error) {
    const message = error.message || '알 수 없는 오류가 발생했습니다';
    this.showError(message);
    this.logError({
      type: 'generic',
      message: message,
      stack: error.stack
    });
    throw error;
  }

  // UI 메시지 표시
  showError(message) {
    if (typeof window.showError === 'function') {
      window.showError(message);
    } else {
      console.error(message);
      alert(message);
    }
  }

  showWarning(message) {
    // 경고 메시지 표시 (에러보다 덜 심각)
    if (typeof window.showWarning === 'function') {
      window.showWarning(message);
    } else if (typeof window.showError === 'function') {
      window.showError(message);
    } else {
      console.warn(message);
    }
  }

  showSuccess(message) {
    if (typeof window.showSuccess === 'function') {
      window.showSuccess(message);
    } else {
      console.log(message);
    }
  }

  // 오프라인 경고 표시
  showOfflineWarning() {
    const existing = document.getElementById('offline-banner');
    if (existing) return;

    const banner = document.createElement('div');
    banner.id = 'offline-banner';
    banner.className = 'offline-banner';
    banner.innerHTML = `
      <div class="offline-content">
        <span class="offline-icon">📡</span>
        <span class="offline-text">오프라인 상태입니다. 인터넷 연결을 확인해주세요.</span>
      </div>
    `;
    document.body.appendChild(banner);
  }

  hideOfflineWarning() {
    const banner = document.getElementById('offline-banner');
    if (banner) {
      banner.classList.add('offline-fadeout');
      setTimeout(() => banner.remove(), 300);
    }
  }

  // 유틸리티
  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  isDevelopment() {
    return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
  }

  // 에러 로그 내보내기
  exportErrorLog() {
    const data = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      total_errors: this.errorLog.length,
      errors: this.errorLog
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metropy-errors-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // 에러 로그 초기화
  clearErrorLog() {
    this.errorLog = [];
    localStorage.removeItem('metropy_error_log');
    this.showSuccess('에러 로그가 초기화되었습니다');
  }

  // 에러 통계
  getErrorStats() {
    const stats = {
      total: this.errorLog.length,
      byType: {},
      recent: this.errorLog.slice(-5)
    };

    this.errorLog.forEach(error => {
      const type = error.type || 'unknown';
      stats.byType[type] = (stats.byType[type] || 0) + 1;
    });

    return stats;
  }
}

// 전역 인스턴스
const errorHandler = new ErrorHandler();

// API 클래스에 에러 핸들러 통합
if (window.API) {
  const originalFetch = window.API.fetch || fetch;

  window.API.fetch = async function(url, options = {}) {
    try {
      return await originalFetch(url, options);
    } catch (error) {
      return await errorHandler.handleAPIError(error, {
        endpoint: url,
        method: options.method,
        retryable: true,
        retryCallback: () => originalFetch(url, options)
      });
    }
  };
}
