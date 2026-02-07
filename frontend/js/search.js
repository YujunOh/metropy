// 고급 검색 기능: 초성 검색 + 퍼지 매칭
class SmartSearch {
  constructor() {
    this.CHO = ["ㄱ","ㄲ","ㄴ","ㄷ","ㄸ","ㄹ","ㅁ","ㅂ","ㅃ","ㅅ","ㅆ","ㅇ","ㅈ","ㅉ","ㅊ","ㅋ","ㅌ","ㅍ","ㅎ"];
  }

  // 한글 초성 추출
  getChosung(text) {
    return text.split('').map(char => {
      const code = char.charCodeAt(0) - 44032;
      if (code > -1 && code < 11172) {
        return this.CHO[Math.floor(code / 588)];
      }
      return char;
    }).join('');
  }

  // 레벤슈타인 거리 (편집 거리)
  levenshteinDistance(str1, str2) {
    const len1 = str1.length;
    const len2 = str2.length;
    const matrix = Array(len1 + 1).fill(null).map(() => Array(len2 + 1).fill(0));

    for (let i = 0; i <= len1; i++) matrix[i][0] = i;
    for (let j = 0; j <= len2; j++) matrix[0][j] = j;

    for (let i = 1; i <= len1; i++) {
      for (let j = 1; j <= len2; j++) {
        const cost = str1[i - 1] === str2[j - 1] ? 0 : 1;
        matrix[i][j] = Math.min(
          matrix[i - 1][j] + 1,
          matrix[i][j - 1] + 1,
          matrix[i - 1][j - 1] + cost
        );
      }
    }

    return matrix[len1][len2];
  }

  // 유사도 점수 계산 (0-1)
  similarity(str1, str2) {
    const maxLen = Math.max(str1.length, str2.length);
    if (maxLen === 0) return 1.0;
    const distance = this.levenshteinDistance(str1.toLowerCase(), str2.toLowerCase());
    return 1.0 - (distance / maxLen);
  }

  // 입력이 전부 초성인지 확인
  isAllChosung(text) {
    return text.split('').every(char => this.CHO.includes(char));
  }

  // 스마트 검색
  search(stations, query) {
    if (!query || query.trim() === '') {
      return stations;
    }

    const q = query.trim().toLowerCase();
    const qChosung = this.getChosung(q);
    const isChosungQuery = this.isAllChosung(q);
    const results = [];

    stations.forEach(station => {
      const name = station.name.toLowerCase();
      const nameDisplay = station.name_display.toLowerCase();
      const chosung = this.getChosung(station.name);

      let score = 0;
      let matchType = '';

      // 1. 정확히 일치 (최고 점수)
      if (name === q || nameDisplay === q) {
        score = 100;
        matchType = 'exact';
      }
      // 2. 시작 부분 일치
      else if (name.startsWith(q) || nameDisplay.startsWith(q)) {
        score = 90;
        matchType = 'prefix';
      }
      // 3. 초성 검색 (세분화된 점수)
      else if (isChosungQuery && chosung.startsWith(qChosung)) {
        // 초성 prefix 일치 - 더 높은 점수
        // 짧은 이름일수록 더 관련성 높음 (ㄱㄴ → 강남 > 강남구청)
        const lengthBonus = Math.max(0, 10 - station.name.length);
        score = 88 + lengthBonus * 0.5;
        matchType = 'chosung-prefix';
      }
      else if (isChosungQuery && chosung.includes(qChosung)) {
        // 초성 부분 일치 - 약간 낮은 점수
        const matchPos = chosung.indexOf(qChosung);
        score = 78 - matchPos * 2; // 뒤에서 매치될수록 낮은 점수
        matchType = 'chosung';
      }
      else if (!isChosungQuery && chosung.includes(qChosung)) {
        // 일반 텍스트의 초성 매치
        score = 75;
        matchType = 'chosung';
      }
      // 4. 부분 일치
      else if (name.includes(q) || nameDisplay.includes(q)) {
        score = 70;
        matchType = 'partial';
      }
      // 5. 퍼지 매칭 (유사도 기반)
      else {
        const sim1 = this.similarity(q, name);
        const sim2 = this.similarity(q, nameDisplay);
        const maxSim = Math.max(sim1, sim2);

        if (maxSim > 0.5) {
          score = maxSim * 60;
          matchType = 'fuzzy';
        }
      }

      if (score > 0) {
        results.push({
          station: station,
          score: score,
          matchType: matchType
        });
      }
    });

    // 점수 순으로 정렬
    results.sort((a, b) => b.score - a.score);

    // 최근 검색 우선순위 (점수 동점 시 우선)
    const recentSearches = this.getRecentSearches();
    results.forEach(result => {
      if (recentSearches.includes(result.station.name)) {
        result.score += 3;
      }
    });

    // 재정렬
    results.sort((a, b) => b.score - a.score);

    return results.slice(0, 10).map(r => r.station);
  }

  getRecentSearches() {
    const history = storage.getHistory();
    const recent = new Set();
    history.forEach(h => {
      recent.add(h.boarding);
      recent.add(h.destination);
    });
    return Array.from(recent);
  }

  // 검색 제안
  getSuggestions(stations, query) {
    if (!query || query.length < 1) {
      return [];
    }

    const results = this.search(stations, query);
    return results.map(station => ({
      text: station.name_display,
      value: station.name,
      highlight: this.highlightMatch(station.name_display, query)
    }));
  }

  // 매치된 부분 하이라이트 (초성 검색도 지원)
  highlightMatch(text, query) {
    // 일반 텍스트 매치 (우선)
    const index = text.toLowerCase().indexOf(query.toLowerCase());
    if (index !== -1) {
      return text.substring(0, index) +
             '<mark>' + text.substring(index, index + query.length) + '</mark>' +
             text.substring(index + query.length);
    }

    // 초성 매치: 초성이 매치되는 글자에 하이라이트
    if (this.isAllChosung(query)) {
      const textChosung = this.getChosung(text);
      const chosungIndex = textChosung.indexOf(query);
      if (chosungIndex !== -1) {
        return text.substring(0, chosungIndex) +
               '<mark>' + text.substring(chosungIndex, chosungIndex + query.length) + '</mark>' +
               text.substring(chosungIndex + query.length);
      }
    }

    return text;
  }
}

// 전역 인스턴스
const smartSearch = new SmartSearch();

// 자동완성 UI
class AutocompleteUI {
  constructor(inputId, selectId, stations) {
    this.input = document.getElementById(inputId);
    this.select = document.getElementById(selectId);
    this.stations = stations;
    this.suggestions = null;
    this._debounceTimer = null;

    this.init();
  }

  init() {
    // 자동완성 컨테이너 생성
    this.suggestions = document.createElement('div');
    this.suggestions.className = 'autocomplete-suggestions';
    this.suggestions.setAttribute('role', 'listbox');
    this.suggestions.style.display = 'none';
    this.input.parentElement.appendChild(this.suggestions);

    // ARIA 속성 추가
    this.input.setAttribute('role', 'combobox');
    this.input.setAttribute('aria-autocomplete', 'list');
    this.input.setAttribute('aria-expanded', 'false');

    // 이벤트 리스너 (디바운스 적용)
    this.input.addEventListener('input', (e) => {
      clearTimeout(this._debounceTimer);
      this._debounceTimer = setTimeout(() => this.handleInput(e), 80);
    });
    this.input.addEventListener('focus', (e) => this.handleInput(e));
    this.input.addEventListener('blur', () => {
      setTimeout(() => this.hideSuggestions(), 200);
    });

    // 키보드 네비게이션
    this.input.addEventListener('keydown', (e) => this.handleKeyboard(e));
  }

  handleInput(e) {
    const query = e.target.value;

    if (!query) {
      this.hideSuggestions();
      this.select.value = '';
      return;
    }

    const results = smartSearch.search(this.stations, query);

    if (results.length === 0) {
      this.showNoResults();
      return;
    }

    this.showSuggestions(results, query);
  }

  showSuggestions(results, query) {
    this.suggestions.innerHTML = results.map((station, index) => {
      const highlighted = smartSearch.highlightMatch(station.name_display, query);
      return `
        <div class="autocomplete-item" data-value="${station.name}" data-index="${index}">
          ${highlighted}
        </div>
      `;
    }).join('');

    // 클릭 이벤트
    this.suggestions.querySelectorAll('.autocomplete-item').forEach(item => {
      item.addEventListener('click', () => {
        this.selectItem(item.dataset.value, item.textContent);
      });
    });

    this.suggestions.style.display = 'block';
    this.input.setAttribute('aria-expanded', 'true');
  }

  showNoResults() {
    this.suggestions.innerHTML = '<div class="autocomplete-no-results">검색 결과가 없습니다</div>';
    this.suggestions.style.display = 'block';
    this.input.setAttribute('aria-expanded', 'true');
  }

  hideSuggestions() {
    this.suggestions.style.display = 'none';
    this.input.setAttribute('aria-expanded', 'false');
  }

  selectItem(value, displayText) {
    this.select.value = value;
    this.input.value = displayText;
    this.hideSuggestions();

    // 변경 이벤트 트리거
    const event = new Event('change', { bubbles: true });
    this.select.dispatchEvent(event);
  }

  handleKeyboard(e) {
    const items = this.suggestions.querySelectorAll('.autocomplete-item');
    if (items.length === 0) return;

    const current = this.suggestions.querySelector('.autocomplete-item.active');
    let index = current ? parseInt(current.dataset.index) : -1;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      index = Math.min(index + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      index = Math.max(index - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (index >= 0) {
        items[index].click();
      }
      return;
    } else if (e.key === 'Escape') {
      this.hideSuggestions();
      return;
    } else {
      return;
    }

    // 활성화 상태 업데이트
    items.forEach(item => item.classList.remove('active'));
    if (index >= 0) {
      items[index].classList.add('active');
      items[index].scrollIntoView({ block: 'nearest' });
    }
  }
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
  // 역 데이터가 로드되면 자동완성 초기화
  let attempts = 0;
  const maxAttempts = 100; // 10초 후 포기
  const checkStations = setInterval(() => {
    attempts++;
    if (window.stations && window.stations.length > 0) {
      clearInterval(checkStations);

      // 출발역 자동완성
      new AutocompleteUI('boarding-search', 'boarding', window.stations);

      // 도착역 자동완성
      new AutocompleteUI('destination-search', 'destination', window.stations);
    } else if (attempts >= maxAttempts) {
      clearInterval(checkStations);
      console.warn('역 데이터 로드 타임아웃 - 자동완성을 초기화할 수 없습니다');
    }
  }, 100);
});
