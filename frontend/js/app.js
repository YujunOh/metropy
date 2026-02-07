// Metropy 메인 컨트롤러
let stations = [];
let lastResult = null;

document.addEventListener('DOMContentLoaded', init);

async function init() {
  try {
    stations = await API.getStations();
    window.stations = stations; // search.js, geolocation.js에서 접근 필요
    populateStationSelects();
    setupEventListeners();
    setDefaultHour();
    setDefaultDow();
    await loadCalibration();
  } catch (e) {
    showError('서버 연결 실패: ' + e.message);
  }
}

// ==================== 페이지 네비게이션 ====================

function showPage(pageName) {
  // 페이지 전환
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(`page-${pageName}`);
  if (target) target.classList.add('active');

  // 네비 링크 활성화
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelector(`.nav-link[data-page="${pageName}"]`)?.classList.add('active');

  // 스크롤 맨 위로
  window.scrollTo(0, 0);

  // 푸터: 랜딩에서만 표시
  const footer = document.getElementById('main-footer');
  if (footer) {
    footer.style.display = pageName === 'landing' || pageName === 'about' ? '' : 'none';
  }
}

function toggleMobileNav() {
  const nav = document.getElementById('mobile-nav');
  if (nav) nav.classList.toggle('open');
}

// ==================== 역 선택 ====================

function populateStationSelects() {
  const boarding = document.getElementById('boarding');
  const destination = document.getElementById('destination');
  [boarding, destination].forEach(sel => {
    sel.innerHTML = '<option value="">역 선택...</option>';
    stations.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.name;
      opt.textContent = s.name_display;
      sel.appendChild(opt);
    });
  });
  // 기본값
  setSelectByValue(boarding, '강남');
  setSelectByValue(destination, '시청');

  // 검색 input에도 기본 역명 표시
  const bs = document.getElementById('boarding-search');
  const ds = document.getElementById('destination-search');
  if (bs && boarding.value) {
    const bStation = stations.find(s => s.name === boarding.value);
    bs.value = bStation ? bStation.name_display : boarding.value;
  }
  if (ds && destination.value) {
    const dStation = stations.find(s => s.name === destination.value);
    ds.value = dStation ? dStation.name_display : destination.value;
  }
}

function setSelectByValue(select, value) {
  for (let opt of select.options) {
    if (opt.value === value) { select.value = value; return; }
  }
}

function swapStations() {
  const b = document.getElementById('boarding');
  const d = document.getElementById('destination');
  const bs = document.getElementById('boarding-search');
  const ds = document.getElementById('destination-search');

  const tmp = b.value;
  b.value = d.value;
  d.value = tmp;

  // 검색 필드도 역명으로 동기화
  if (bs && b.value) {
    const station = stations.find(s => s.name === b.value);
    bs.value = station ? station.name_display : b.value;
  } else if (bs) { bs.value = ''; }
  if (ds && d.value) {
    const station = stations.find(s => s.name === d.value);
    ds.value = station ? station.name_display : d.value;
  } else if (ds) { ds.value = ''; }
}

function filterStations(selectId, query) {
  const select = document.getElementById(selectId);
  const current = select.value;
  select.innerHTML = '<option value="">역 선택...</option>';

  const q = query.trim().toLowerCase();
  const filtered = q
    ? stations.filter(s => s.name.includes(q) || s.name_display.includes(q))
    : stations;

  filtered.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s.name;
    opt.textContent = s.name_display;
    select.appendChild(opt);
  });
  if (current) setSelectByValue(select, current);
}

// ==================== 이벤트 리스너 ====================

function setupEventListeners() {
  document.getElementById('recommend-btn').addEventListener('click', doRecommend);
  document.getElementById('hour-slider').addEventListener('input', updateHourLabel);

  // 캘리브레이션 슬라이더
  document.getElementById('beta-slider')?.addEventListener('input', (e) => {
    document.getElementById('beta-value').textContent = parseFloat(e.target.value).toFixed(2);
  });
  document.getElementById('apply-calibration')?.addEventListener('click', applyCalibration);
  document.getElementById('reset-calibration')?.addEventListener('click', resetCalibration);
  document.getElementById('sensitivity-btn')?.addEventListener('click', doSensitivity);

  // 역 검색은 search.js의 AutocompleteUI가 처리
  // select 변경 시 검색 input 동기화
  document.getElementById('boarding')?.addEventListener('change', () => {
    const sel = document.getElementById('boarding');
    const input = document.getElementById('boarding-search');
    if (sel.value && input) {
      const station = stations.find(s => s.name === sel.value);
      input.value = station ? station.name_display : sel.value;
    }
  });
  document.getElementById('destination')?.addEventListener('change', () => {
    const sel = document.getElementById('destination');
    const input = document.getElementById('destination-search');
    if (sel.value && input) {
      const station = stations.find(s => s.name === sel.value);
      input.value = station ? station.name_display : sel.value;
    }
  });

  // 시간 팁 클릭 핸들러
  document.querySelectorAll('.hour-tips .tip').forEach(tip => {
    tip.addEventListener('click', () => {
      const hour = parseInt(tip.dataset.hour);
      if (!isNaN(hour)) {
        document.getElementById('hour-slider').value = hour;
        updateHourLabel();
      }
    });
  });

  // 요일 칩 클릭 핸들러
  document.querySelectorAll('.dow-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.dow-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
    });
  });
}

// ==================== 요일 선택 ====================

function setDefaultDow() {
  const days = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const todayDow = days[new Date().getDay()];
  const autoChip = document.querySelector('.dow-chip[data-dow=""]');
  if (autoChip) {
    const dowLabels = { MON:'월', TUE:'화', WED:'수', THU:'목', FRI:'금', SAT:'토', SUN:'일' };
    autoChip.textContent = `오늘(${dowLabels[todayDow]})`;
    autoChip.dataset.autoDow = todayDow;
  }
}

function getSelectedDow() {
  const active = document.querySelector('.dow-chip.active');
  if (!active) return null;
  const dow = active.dataset.dow;
  if (dow === '') return active.dataset.autoDow || null;
  return dow || null;
}

// ==================== 시간 선택 ====================

function setDefaultHour() {
  const hour = new Date().getHours();
  // 00:00~01:00은 24~25로 매핑, 그 외는 5~23 범위
  let sliderValue;
  if (hour === 0) sliderValue = 24;
  else if (hour === 1) sliderValue = 25;
  else sliderValue = Math.max(5, Math.min(23, hour));

  const slider = document.getElementById('hour-slider');
  slider.value = sliderValue;
  updateHourLabel();
}

function updateHourLabel() {
  const sliderValue = parseInt(document.getElementById('hour-slider').value);
  const label = document.getElementById('hour-label');
  const period = getTimePeriod(sliderValue);

  // 24→00:00, 25→01:00 (막차 시간대)
  const displayHour = sliderValue >= 24 ? sliderValue - 24 : sliderValue;
  const timeStr = `${String(displayHour).padStart(2, '0')}:00`;

  // 새 구조: hour-time + hour-period
  const timeEl = label.querySelector('.hour-time');
  const periodEl = label.querySelector('.hour-period');
  if (timeEl && periodEl) {
    timeEl.textContent = timeStr;
    periodEl.textContent = period;
  } else {
    label.textContent = `${timeStr} (${period})`;
  }
}

function adjustHour(delta) {
  const slider = document.getElementById('hour-slider');
  let val = parseInt(slider.value) + delta;
  val = Math.max(parseInt(slider.min), Math.min(parseInt(slider.max), val));
  slider.value = val;
  updateHourLabel();
}

function getTimePeriod(hour) {
  // 24, 25는 막차 시간대 (00:00, 01:00)
  if (hour >= 24) return '막차';
  if (hour >= 7 && hour < 9) return '출근 러시';
  if (hour >= 18 && hour < 20) return '퇴근 러시';
  if (hour >= 10 && hour < 18) return '주간';
  if (hour >= 20 && hour < 22) return '저녁';
  if (hour >= 22) return '심야';
  if (hour < 6) return '첫차';
  return '새벽';
}

// ==================== 추천 ====================

async function doRecommend() {
  const boarding = document.getElementById('boarding').value;
  const destination = document.getElementById('destination').value;
  const hour = parseInt(document.getElementById('hour-slider').value);

  if (!boarding || !destination) {
    showError('출발역과 도착역을 선택해주세요.');
    return;
  }
  if (boarding === destination) {
    showError('출발역과 도착역이 같습니다.');
    return;
  }

  const btn = document.getElementById('recommend-btn');
  btn.disabled = true;
  btn.classList.add('loading');
  btn.innerHTML = '<span class="btn-icon">⏳</span> 분석 중...';
  hideError();

  // 스켈레톤 로딩 표시
  showSkeletonLoading();

  try {
    const dow = getSelectedDow();
    const result = await API.recommend(boarding, destination, hour, null, dow);
    lastResult = result;

    // 통계 업데이트
    storage.incrementRecommendation(
      { boarding, destination, hour },
      result.best_car
    );

    // 히스토리에 추가
    storage.addHistory({
      boarding,
      destination,
      hour,
      direction: result.direction
    });

    displayResult(result);
  } catch (e) {
    hideSkeletonLoading();
    showError(e.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
    btn.innerHTML = '<span class="btn-icon">&#9658;</span> 최적 칸 추천';
  }
}

// 스켈레톤 로딩 표시
function showSkeletonLoading() {
  const section = document.getElementById('result-section');
  section.classList.add('visible');

  // 스켈레톤 HTML
  section.innerHTML = `
    <div class="skeleton-hero">
      <div class="skeleton skeleton-hero-main"></div>
      <div class="skeleton-hero-meta">
        <div class="skeleton skeleton-meta-item"></div>
        <div class="skeleton skeleton-meta-item"></div>
        <div class="skeleton skeleton-meta-item"></div>
        <div class="skeleton skeleton-meta-item"></div>
        <div class="skeleton skeleton-meta-item"></div>
      </div>
    </div>

    <div class="card">
      <div class="skeleton skeleton-text medium"></div>
      <div class="skeleton-train">
        ${Array(10).fill('<div class="skeleton-car"></div>').join('')}
      </div>
    </div>

    <div class="card">
      <div class="skeleton skeleton-text short"></div>
      <div class="skeleton" style="height:200px;margin-top:16px"></div>
    </div>
  `;
}

// 스켈레톤 로딩 숨기기
function hideSkeletonLoading() {
  const section = document.getElementById('result-section');
  section.classList.remove('visible');
  section.innerHTML = '';
}

function displayResult(result) {
  const section = document.getElementById('result-section');

  // 스켈레톤 로딩 후 원래 구조 복원
  section.innerHTML = `
    <div class="result-hero" id="result-hero">
      <div class="result-best">
        <span class="result-best-label">추천</span>
        <span class="result-best-car" id="best-car-num"></span>
        <span class="result-best-score" id="best-car-score"></span>
      </div>
      <div class="result-meta" id="result-meta"></div>
    </div>

    <div class="card">
      <div class="card-header">
        <div>
          <h2 class="card-title">칸별 SeatScore</h2>
          <p class="card-desc">칸을 클릭하면 상세 정보를 볼 수 있습니다</p>
        </div>
        <button class="quick-explain-btn" onclick="showBestCarExplanation()" id="quick-explain-btn">
          <span>💡</span> 왜 이 칸인가요?
        </button>
      </div>
      <div id="train-viz"></div>
      <div id="car-detail"></div>
    </div>

    <div class="card" id="score-chart-card"></div>
    <div class="card" id="bp-chart"></div>
    <div class="card" id="route-info"></div>

    <div class="card" id="route-compare-card">
      <div class="card-header">
        <h2 class="card-title">경로 비교</h2>
        <button class="btn-secondary" onclick="toggleCompareMode()" id="compare-toggle-btn">
          + 다른 경로와 비교
        </button>
      </div>
      <div id="compare-section" style="display:none">
        <div class="compare-input-row">
          <div class="input-group">
            <label>비교 출발역</label>
            <input type="text" id="compare-boarding-search" class="station-search" placeholder="역명 검색..." autocomplete="off">
            <select id="compare-boarding" class="station-select"></select>
          </div>
          <div class="input-group">
            <label>비교 도착역</label>
            <input type="text" id="compare-destination-search" class="station-search" placeholder="역명 검색..." autocomplete="off">
            <select id="compare-destination" class="station-select"></select>
          </div>
          <button class="btn-primary" onclick="runComparison()">비교하기</button>
        </div>
        <div id="comparison-result"></div>
      </div>
    </div>
  `;

  section.classList.add('visible');

  // 전역 저장 (explanation.js에서 사용)
  window.lastRecommendationData = result;

  // 핵심 결과 히어로
  document.getElementById('best-car-num').textContent = `${result.best_car}호차`;
  document.getElementById('best-car-score').textContent = `${result.best_score.toFixed(1)}점`;

  // 메타 정보
  const dowLabels = { MON:'월요일', TUE:'화요일', WED:'수요일', THU:'목요일', FRI:'금요일', SAT:'토요일', SUN:'일요일' };
  const dowDisplay = result.dow ? dowLabels[result.dow] || result.dow : '평일(기본)';

  document.getElementById('result-meta').innerHTML = `
    <div class="meta-item">
      <span class="meta-label">경로</span>
      <span class="meta-value">${result.boarding} → ${result.destination}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">방향</span>
      <span class="meta-value">${result.direction} (경유 ${result.n_intermediate}개역)</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">요일</span>
      <span class="meta-value">${dowDisplay}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">시간대 배율 α</span>
      <span class="meta-value">${result.alpha}</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">비추천 칸</span>
      <span class="meta-value">${result.worst_car}호차 (${result.worst_score}점)</span>
    </div>
    <div class="meta-item">
      <span class="meta-label">최대-최소 차이</span>
      <span class="meta-value">${result.score_spread}점</span>
    </div>
  `;

  // 열차 시각화
  renderTrain(result.car_scores);

  // 점수 분포 차트 추가 (새로운 카드)
  const existingScoreChart = document.getElementById('score-chart-card');
  if (!existingScoreChart) {
    const scoreCard = document.createElement('div');
    scoreCard.className = 'card';
    scoreCard.id = 'score-chart-card';
    document.getElementById('result-section').insertBefore(
      scoreCard,
      document.getElementById('bp-chart')
    );
  }
  renderScoreDistributionChart(result.car_scores, 'score-chart-card');

  // Benefit/Penalty 차트
  renderBenefitPenaltyChart(result.car_scores);

  // 경유역 표시
  document.getElementById('route-info').innerHTML = `
    <h2 class="card-title">경유역</h2>
    <div class="route-stations">
      ${result.intermediates.map(s => `<span class="station-chip">${s}</span>`).join(' → ')}
    </div>
  `;

  // 지도 업데이트 (지도가 열려있는 경우)
  updateMapWithResult(result);
}

// ==================== 캘리브레이션 ====================

async function loadCalibration() {
  try {
    const cal = await API.getCalibration();
    document.getElementById('beta-slider').value = cal.beta;
    document.getElementById('beta-value').textContent = parseFloat(cal.beta).toFixed(2);
    document.getElementById('w-escalator').value = cal.facility_weights['에스컬레이터'] || 1.5;
    document.getElementById('w-elevator').value = cal.facility_weights['엘리베이터'] || 1.2;
    document.getElementById('w-stairs').value = cal.facility_weights['계단'] || 1.0;
    document.getElementById('a-morning').value = cal.alpha_map.morning_rush || 1.4;
    document.getElementById('a-evening').value = cal.alpha_map.evening_rush || 1.3;
    document.getElementById('a-midday').value = cal.alpha_map.midday || 1.0;
    document.getElementById('a-night').value = cal.alpha_map.night || 0.6;
  } catch (e) { /* ignore on first load */ }
}

async function applyCalibration() {
  const params = {
    beta: parseFloat(document.getElementById('beta-slider').value),
    escalator_weight: parseFloat(document.getElementById('w-escalator').value),
    elevator_weight: parseFloat(document.getElementById('w-elevator').value),
    stairs_weight: parseFloat(document.getElementById('w-stairs').value),
    alpha_morning_rush: parseFloat(document.getElementById('a-morning').value),
    alpha_evening_rush: parseFloat(document.getElementById('a-evening').value),
    alpha_midday: parseFloat(document.getElementById('a-midday').value),
    alpha_night: parseFloat(document.getElementById('a-night').value),
  };

  try {
    await API.setCalibration(params);
    showSuccess('파라미터가 적용되었습니다.');
    if (lastResult) await doRecommend();
  } catch (e) {
    showError('캘리브레이션 실패: ' + e.message);
  }
}

async function resetCalibration() {
  const defaults = {
    beta: 0.3,
    escalator_weight: 1.5,
    elevator_weight: 1.2,
    stairs_weight: 1.0,
    alpha_morning_rush: 1.4,
    alpha_evening_rush: 1.3,
    alpha_midday: 1.0,
    alpha_night: 0.6,
  };
  await API.setCalibration(defaults);
  await loadCalibration();
  showSuccess('기본값으로 초기화되었습니다.');
  if (lastResult) await doRecommend();
}

// ==================== 민감도 분석 ====================

async function doSensitivity() {
  const boarding = document.getElementById('boarding').value;
  const destination = document.getElementById('destination').value;
  const hour = parseInt(document.getElementById('hour-slider').value);

  if (!boarding || !destination) {
    showError('먼저 추천 탭에서 출발역과 도착역을 선택해주세요.');
    return;
  }

  const btn = document.getElementById('sensitivity-btn');
  btn.disabled = true;
  btn.textContent = '분석 중...';

  try {
    const data = await API.getSensitivity(boarding, destination, hour);
    renderSensitivityChart(data);
  } catch (e) {
    showError('민감도 분석 실패: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'β 민감도 분석 실행';
  }
}

function renderSensitivityChart(data) {
  const container = document.getElementById('sensitivity-chart');
  if (!container) return;

  // 칸별로 그룹화
  const byCar = {};
  data.forEach(d => {
    if (!byCar[d.car]) byCar[d.car] = [];
    byCar[d.car].push(d);
  });

  const colors = [
    '#e74c3c','#e67e22','#f1c40f','#2ecc71','#1abc9c',
    '#3498db','#9b59b6','#e91e63','#795548','#607d8b'
  ];

  // SVG 차트
  const W = 600, H = 300, PAD = 50;
  const plotW = W - PAD * 2, plotH = H - PAD * 2;

  let svg = `<svg viewBox="0 0 ${W} ${H}" class="sensitivity-svg">`;

  // 축
  svg += `<line x1="${PAD}" y1="${H-PAD}" x2="${W-PAD}" y2="${H-PAD}" stroke="var(--border)" stroke-width="1"/>`;
  svg += `<line x1="${PAD}" y1="${PAD}" x2="${PAD}" y2="${H-PAD}" stroke="var(--border)" stroke-width="1"/>`;

  // X축 레이블
  for (let b = 0; b <= 100; b += 20) {
    const x = PAD + (b / 100) * plotW;
    svg += `<text x="${x}" y="${H-PAD+18}" text-anchor="middle" font-size="11" fill="var(--text-dim)">${(b/100).toFixed(1)}</text>`;
  }
  svg += `<text x="${W/2}" y="${H-5}" text-anchor="middle" font-size="12" fill="var(--text-sub)">β (penalty coefficient)</text>`;

  // Y축 레이블
  for (let s = 0; s <= 100; s += 20) {
    const y = H - PAD - (s / 100) * plotH;
    svg += `<text x="${PAD-8}" y="${y+4}" text-anchor="end" font-size="11" fill="var(--text-dim)">${s}</text>`;
  }
  svg += `<text x="15" y="${H/2}" text-anchor="middle" font-size="12" fill="var(--text-sub)" transform="rotate(-90,15,${H/2})">Score</text>`;

  // 각 칸의 라인
  Object.entries(byCar).forEach(([car, points], idx) => {
    const pathParts = points.map(p => {
      const x = PAD + (p.beta / 1.0) * plotW;
      const y = H - PAD - (p.score / 100) * plotH;
      return `${x},${y}`;
    });
    svg += `<polyline points="${pathParts.join(' ')}" fill="none" stroke="${colors[idx % 10]}" stroke-width="2" opacity="0.8"/>`;

    // 끝점에 라벨
    const last = points[points.length - 1];
    const lx = PAD + (last.beta / 1.0) * plotW + 5;
    const ly = H - PAD - (last.score / 100) * plotH;
    svg += `<text x="${lx}" y="${ly+4}" font-size="10" fill="${colors[idx % 10]}">${car}</text>`;
  });

  svg += '</svg>';

  // 범례
  let legend = '<div class="sensitivity-legend">';
  Object.keys(byCar).forEach((car, idx) => {
    legend += `<span style="color:${colors[idx % 10]}">■ ${car}호차</span> `;
  });
  legend += '</div>';

  container.innerHTML = svg + legend;
}

// ==================== 유틸리티 ====================

function showError(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.className = 'message error visible';
}

function hideError() {
  const el = document.getElementById('error-msg');
  el.className = 'message';
}

function showLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.add('visible');
}

function hideLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.remove('visible');
}

function showSuccess(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.className = 'message success visible';
  setTimeout(() => { el.className = 'message'; }, 2000);
}

// 최적 칸 빠른 설명 표시
function showBestCarExplanation() {
  const result = window.lastRecommendationData;
  if (!result || !result.car_scores) {
    showError('추천 결과가 없습니다. 먼저 경로를 검색해주세요.');
    return;
  }

  // 최적 칸 데이터 찾기
  const bestCar = result.car_scores.find(c => c.rank === 1);
  if (bestCar && typeof showCarExplanation === 'function') {
    showCarExplanation(bestCar, result);
  }
}

// ==================== 지도 ====================

let mapInitialized = false;

function toggleMapView() {
  const container = document.getElementById('metro-map');
  const toggleText = document.getElementById('map-toggle-text');
  const toggleIcon = document.getElementById('map-toggle-icon');

  if (!container) return;

  const isVisible = container.classList.contains('map-visible');

  if (isVisible) {
    // 숨기기
    container.classList.remove('map-visible');
    container.style.height = '0';
    if (toggleText) toggleText.textContent = '지도 펼치기';
    if (toggleIcon) toggleIcon.textContent = '📍';
  } else {
    // 펼치기
    container.classList.add('map-visible');
    container.style.height = '400px';
    if (toggleText) toggleText.textContent = '지도 접기';
    if (toggleIcon) toggleIcon.textContent = '🗺️';

    // 지도 초기화
    if (!mapInitialized && typeof MetroMap !== 'undefined') {
      setTimeout(() => {
        if (MetroMap.init('metro-map')) {
          mapInitialized = true;

          // 현재 선택된 경로가 있으면 표시
          showCurrentRouteOnMap();
        }
      }, 150);
    } else if (mapInitialized && typeof MetroMap !== 'undefined') {
      // 이미 초기화됨 - 경로만 업데이트
      showCurrentRouteOnMap();
    }
  }
}

function showCurrentRouteOnMap() {
  if (!mapInitialized || typeof MetroMap === 'undefined') return;

  const boarding = document.getElementById('boarding')?.value;
  const destination = document.getElementById('destination')?.value;

  if (boarding && destination && boarding !== destination) {
    // 마지막 추천 결과가 있으면 경유역도 표시
    const result = window.lastRecommendationData;
    const intermediates = result?.intermediates || [];

    MetroMap.highlightRoute(boarding, destination, intermediates);
  } else {
    MetroMap.showFullLine();
  }
}

// 추천 결과가 표시될 때 지도에도 경로 표시
function updateMapWithResult(result) {
  if (!mapInitialized || typeof MetroMap === 'undefined') return;

  const container = document.getElementById('metro-map');
  if (container && container.classList.contains('map-visible')) {
    MetroMap.highlightRoute(result.boarding, result.destination, result.intermediates);
  }
}
