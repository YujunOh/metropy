// 터치 제스처 지원 모듈
class TouchHandler {
  constructor() {
    this.touchStartX = 0;
    this.touchEndX = 0;
    this.touchStartY = 0;
    this.touchEndY = 0;
    this.minSwipeDistance = 50;
  }

  init() {
    // 열차 칸 스와이프 지원
    this.initTrainSwipe();

    // 페이지 스와이프 네비게이션 (선택사항)
    // this.initPageSwipe();

    // Pull to refresh 방지 (필요시)
    this.preventPullToRefresh();
  }

  initTrainSwipe() {
    const train = document.querySelector('.train');
    if (!train) return;

    let isDragging = false;
    let startX = 0;
    let scrollLeft = 0;

    train.addEventListener('touchstart', (e) => {
      isDragging = true;
      startX = e.touches[0].pageX - train.offsetLeft;
      scrollLeft = train.scrollLeft;
    }, { passive: true });

    train.addEventListener('touchmove', (e) => {
      if (!isDragging) return;
      const x = e.touches[0].pageX - train.offsetLeft;
      const walk = (x - startX) * 2; // 스크롤 속도
      train.scrollLeft = scrollLeft - walk;
    }, { passive: true });

    train.addEventListener('touchend', () => {
      isDragging = false;
    }, { passive: true });
  }

  preventPullToRefresh() {
    // iOS Safari pull-to-refresh 방지 (앱 페이지에서만)
    let lastTouchY = 0;
    let preventPullToRefresh = false;

    document.addEventListener('touchstart', (e) => {
      if (e.touches.length !== 1) return;
      lastTouchY = e.touches[0].clientY;
      preventPullToRefresh = window.pageYOffset === 0;
    }, { passive: false });

    document.addEventListener('touchmove', (e) => {
      const touchY = e.touches[0].clientY;
      const touchYDelta = touchY - lastTouchY;
      lastTouchY = touchY;

      if (preventPullToRefresh) {
        // 아래로 스크롤하려는 시도 방지
        if (touchYDelta > 0) {
          e.preventDefault();
          return;
        }
        preventPullToRefresh = false;
      }
    }, { passive: false });
  }

  // 스와이프 방향 감지
  handleSwipe(element, callbacks) {
    element.addEventListener('touchstart', (e) => {
      this.touchStartX = e.changedTouches[0].screenX;
      this.touchStartY = e.changedTouches[0].screenY;
    }, { passive: true });

    element.addEventListener('touchend', (e) => {
      this.touchEndX = e.changedTouches[0].screenX;
      this.touchEndY = e.changedTouches[0].screenY;
      this.detectSwipeDirection(callbacks);
    }, { passive: true });
  }

  detectSwipeDirection(callbacks) {
    const deltaX = this.touchEndX - this.touchStartX;
    const deltaY = this.touchEndY - this.touchStartY;

    // 수평 스와이프가 더 큰 경우
    if (Math.abs(deltaX) > Math.abs(deltaY)) {
      if (Math.abs(deltaX) > this.minSwipeDistance) {
        if (deltaX > 0 && callbacks.onSwipeRight) {
          callbacks.onSwipeRight();
        } else if (deltaX < 0 && callbacks.onSwipeLeft) {
          callbacks.onSwipeLeft();
        }
      }
    }
    // 수직 스와이프가 더 큰 경우
    else {
      if (Math.abs(deltaY) > this.minSwipeDistance) {
        if (deltaY > 0 && callbacks.onSwipeDown) {
          callbacks.onSwipeDown();
        } else if (deltaY < 0 && callbacks.onSwipeUp) {
          callbacks.onSwipeUp();
        }
      }
    }
  }

  // 롱 프레스 감지
  handleLongPress(element, callback, duration = 500) {
    let timer;

    element.addEventListener('touchstart', (e) => {
      timer = setTimeout(() => {
        callback(e);
      }, duration);
    }, { passive: true });

    element.addEventListener('touchend', () => {
      clearTimeout(timer);
    }, { passive: true });

    element.addEventListener('touchmove', () => {
      clearTimeout(timer);
    }, { passive: true });
  }

  // 핀치 줌 감지 (필요시 차트 확대용)
  handlePinch(element, callbacks) {
    let initialDistance = 0;

    element.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        initialDistance = this.getDistance(e.touches[0], e.touches[1]);
      }
    }, { passive: true });

    element.addEventListener('touchmove', (e) => {
      if (e.touches.length === 2) {
        const currentDistance = this.getDistance(e.touches[0], e.touches[1]);
        const scale = currentDistance / initialDistance;

        if (scale > 1.1 && callbacks.onPinchOut) {
          callbacks.onPinchOut(scale);
        } else if (scale < 0.9 && callbacks.onPinchIn) {
          callbacks.onPinchIn(scale);
        }
      }
    }, { passive: true });
  }

  getDistance(touch1, touch2) {
    const dx = touch1.clientX - touch2.clientX;
    const dy = touch1.clientY - touch2.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  // 진동 피드백 (지원되는 경우)
  vibrate(pattern = [10]) {
    if ('vibrate' in navigator) {
      navigator.vibrate(pattern);
    }
  }
}

// 전역 인스턴스
const touchHandler = new TouchHandler();

// DOM 로드 후 초기화
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => touchHandler.init());
} else {
  touchHandler.init();
}
