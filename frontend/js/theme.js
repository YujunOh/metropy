// 테마 관리 모듈
(function() {
  const THEME_KEY = 'metropy_theme';

  // 저장된 테마 또는 시스템 설정 가져오기
  function getPreferredTheme() {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved) return saved;

    // 시스템 설정 확인
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      return 'light';
    }
    return 'dark';
  }

  // 테마 적용
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);

    // 모바일 메뉴 아이콘 업데이트
    const mobileIcon = document.getElementById('mobile-theme-icon');
    if (mobileIcon) {
      mobileIcon.textContent = theme === 'light' ? '☀️' : '🌙';
    }

    // meta theme-color 업데이트
    const themeColor = document.querySelector('meta[name="theme-color"]');
    if (themeColor) {
      themeColor.content = theme === 'light' ? '#4a7cf5' : '#5b8cff';
    }
  }

  // 테마 토글
  window.toggleTheme = function() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    applyTheme(next);
  };

  // 초기화: DOM 로드 전에 테마 적용 (깜빡임 방지)
  applyTheme(getPreferredTheme());

  // 시스템 테마 변경 감지
  if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
      if (!localStorage.getItem(THEME_KEY)) {
        applyTheme(e.matches ? 'light' : 'dark');
      }
    });
  }
})();
