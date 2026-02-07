// 키보드 단축키 모듈
class KeyboardShortcuts {
  constructor() {
    this.shortcuts = {
      'r': () => this.focusRecommend(),
      'h': () => this.goHome(),
      's': () => this.goSettings(),
      'a': () => this.goApp(),
      'f': () => this.toggleFavorite(),
      '/': () => this.focusSearch(),
      '?': () => this.showHelp(),
      'Escape': () => this.closeModals()
    };

    this.init();
  }

  init() {
    document.addEventListener('keydown', (e) => {
      // Ctrl+K / Cmd+K: 글로벌 검색 포커스 (어디서든 작동)
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        showPage('app');
        setTimeout(() => {
          const search = document.getElementById('boarding-search');
          if (search) { search.focus(); search.select(); }
        }, 50);
        return;
      }

      // input/textarea에서는 일반 단축키 무시
      if (e.target.matches('input, textarea, select')) {
        if (e.key === 'Escape') {
          e.target.blur();
        }
        return;
      }

      // 다른 Ctrl/Cmd 조합은 무시
      if (e.ctrlKey || e.metaKey) return;

      const handler = this.shortcuts[e.key];
      if (handler) {
        e.preventDefault();
        handler();
      }
    });
  }

  focusRecommend() {
    const btn = document.getElementById('recommend-btn');
    if (btn && btn.offsetParent !== null) {
      btn.click();
    }
  }

  goHome() {
    showPage('landing');
  }

  goSettings() {
    showPage('calibrate');
  }

  goApp() {
    showPage('app');
  }

  toggleFavorite() {
    const btn = document.getElementById('add-favorite-btn');
    if (btn && btn.offsetParent !== null) {
      btn.click();
    }
  }

  focusSearch() {
    const search = document.getElementById('boarding-search');
    if (search && search.offsetParent !== null) {
      search.focus();
    }
  }

  showHelp() {
    const helpHTML = `
      <div class="modal-overlay" id="help-modal" onclick="if(event.target === this) this.remove()">
        <div class="modal-content">
          <h2 style="margin-bottom:20px">⌨️ 키보드 단축키</h2>
          <div class="shortcuts-grid">
            <div class="shortcut-item"><kbd>Ctrl</kbd>+<kbd>K</kbd><span>빠른 검색 (어디서든)</span></div>
            <div class="shortcut-item"><kbd>R</kbd><span>추천 실행</span></div>
            <div class="shortcut-item"><kbd>H</kbd><span>홈으로</span></div>
            <div class="shortcut-item"><kbd>A</kbd><span>추천 페이지</span></div>
            <div class="shortcut-item"><kbd>S</kbd><span>설정</span></div>
            <div class="shortcut-item"><kbd>F</kbd><span>즐겨찾기 토글</span></div>
            <div class="shortcut-item"><kbd>/</kbd><span>검색 포커스</span></div>
            <div class="shortcut-item"><kbd>?</kbd><span>도움말</span></div>
            <div class="shortcut-item"><kbd>ESC</kbd><span>닫기</span></div>
          </div>
          <button class="btn-primary" onclick="document.getElementById('help-modal').remove()" style="margin-top:20px;width:100%">닫기</button>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', helpHTML);
  }

  closeModals() {
    const modals = document.querySelectorAll('.modal-overlay');
    modals.forEach(m => m.remove());

    const loading = document.getElementById('loading-overlay');
    if (loading) loading.classList.remove('visible');
  }
}

// 전역 인스턴스
const keyboard = new KeyboardShortcuts();
