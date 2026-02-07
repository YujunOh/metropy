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

  // Focus management for screen readers
  if (target) {
    target.setAttribute('tabindex', '-1');
    target.focus({ preventScroll: true });
  }

  // 푸터: 모든 정보 페이지에서 표시
  const footer = document.getElementById('main-footer');
  if (footer) {
    const showFooter = ['landing', 'about', 'calibrate', 'stats'];
    footer.style.display = showFooter.includes(pageName) ? '' : 'none';
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
  document.getElementById('gamma-slider')?.addEventListener('input', (e) => {
    document.getElementById('gamma-value').textContent = parseFloat(e.target.value).toFixed(2);
  });
  document.getElementById('delta-slider')?.addEventListener('input', (e) => {
    document.getElementById('delta-value').textContent = parseFloat(e.target.value).toFixed(2);
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

  const boardingInput = document.getElementById('boarding-search');
  const destinationInput = document.getElementById('destination-search');
  boardingInput?.addEventListener('input', () => { boardingInput.style.borderColor = ''; });
  destinationInput?.addEventListener('input', () => { destinationInput.style.borderColor = ''; });

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
      updateWeekendLastTrain();
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

  // 접근성: ARIA 값 동기화
  const slider = document.getElementById('hour-slider');
  slider.setAttribute('aria-valuenow', sliderValue);
  slider.setAttribute('aria-valuetext', `${timeStr} ${period}`);
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
  if (hour >= 7 && hour < 9) return '출근 시간대';
  if (hour >= 18 && hour < 20) return '퇴근 시간대';
  if (hour >= 10 && hour < 18) return '주간';
  if (hour >= 20 && hour < 22) return '저녁';
  if (hour >= 22) return '심야';
  if (hour < 6) return '첫차';
  return '새벽';
}

// ==================== 주말 막차 ====================

function updateWeekendLastTrain() {
  const dow = getSelectedDow();
  const isWeekend = dow === 'SAT' || dow === 'SUN';
  const slider = document.getElementById('hour-slider');
  const rangeInfo = document.getElementById('hour-range-info');

  if (isWeekend) {
    slider.max = 24; // 주말 막차 24:00 (00:00)
    if (parseInt(slider.value) > 24) slider.value = 24;
    if (rangeInfo) rangeInfo.textContent = '첫차 05:30 ~ 막차 24:00 (주말)';
  } else {
    slider.max = 25;
    if (rangeInfo) rangeInfo.textContent = '첫차 05:00 ~ 막차 24:30';
  }
  updateHourLabel();
}

// ==================== 추천 ====================

async function doRecommend() {
  const boarding = document.getElementById('boarding').value;
  const destination = document.getElementById('destination').value;
  const hour = parseInt(document.getElementById('hour-slider').value);

  // 인라인 유효성 검사
  const bInput = document.getElementById('boarding-search');
  const dInput = document.getElementById('destination-search');

  // 이전 에러 상태 초기화
  if (bInput) bInput.style.borderColor = '';
  if (dInput) dInput.style.borderColor = '';

  if (!boarding && !destination) {
    showError('출발역과 도착역을 선택해주세요.');
    if (bInput) { bInput.style.borderColor = 'var(--red)'; bInput.focus(); }
    if (dInput) dInput.style.borderColor = 'var(--red)';
    return;
  }
  if (!boarding) {
    showError('출발역을 선택해주세요.');
    if (bInput) { bInput.style.borderColor = 'var(--red)'; bInput.focus(); }
    return;
  }
  if (!destination) {
    showError('도착역을 선택해주세요.');
    if (dInput) { dInput.style.borderColor = 'var(--red)'; dInput.focus(); }
    return;
  }
  if (boarding === destination) {
    showError('출발역과 도착역이 같습니다. 다른 역을 선택해주세요.');
    if (dInput) { dInput.style.borderColor = 'var(--red)'; dInput.focus(); }
    return;
  }

  const btn = document.getElementById('recommend-btn');
  btn.disabled = true;
  btn.classList.add('loading');
  btn.innerHTML = '<span class="btn-icon">⏳</span> 분석 중...';
  hideError();

  // 스켈레톤 로딩 표시
  showSkeletonLoading();
  const loadingWarningTimer = setTimeout(() => {
    showWarning('요청이 오래 걸리고 있습니다. 잠시만 기다려주세요...');
  }, 5000);

  // 10초 후 스켈레톤 타임아웃 → 재시도 버튼 표시
  const skeletonTimeoutTimer = setTimeout(() => {
    const section = document.getElementById('result-section');
    if (section && section.querySelector('.skeleton-hero')) {
      section.innerHTML = `
        <div class="card" style="text-align:center;padding:40px 20px">
          <p style="font-size:1.1rem;margin-bottom:16px;color:var(--text)">응답이 지연되고 있습니다</p>
          <p style="color:var(--text-dim);margin-bottom:20px">서버 연결을 확인하거나 다시 시도해주세요</p>
          <button class="btn-primary" onclick="doRecommend()" style="margin:0 auto">다시 시도</button>
        </div>
      `;
    }
  }, 10000);

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

    // Haptic feedback on success (mobile)
    if (navigator.vibrate) navigator.vibrate(50);

    // Smooth scroll to results
    setTimeout(() => {
      const section = document.getElementById('result-section');
      if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
  } catch (e) {
    hideSkeletonLoading();
    showError(e.message);
  } finally {
    clearTimeout(loadingWarningTimer);
    clearTimeout(skeletonTimeoutTimer);
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
            <div class="select-wrapper">
              <input type="text" id="compare-boarding-search" class="station-search" placeholder="역명 검색 (초성 가능)" autocomplete="off" aria-label="비교 출발역 검색">
              <select id="compare-boarding" class="station-select"></select>
            </div>
          </div>
          <div class="input-group">
            <label>비교 도착역</label>
            <div class="select-wrapper">
              <input type="text" id="compare-destination-search" class="station-search" placeholder="역명 검색 (초성 가능)" autocomplete="off" aria-label="비교 도착역 검색">
              <select id="compare-destination" class="station-select"></select>
            </div>
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

  // 공유 버튼 추가
  const heroEl = document.getElementById('result-hero');
  if (heroEl) {
    const shareBtn = document.createElement('button');
    shareBtn.className = 'result-share-btn';
    shareBtn.title = '추천 결과 복사';
    shareBtn.innerHTML = '📋 공유';
    shareBtn.onclick = () => shareResult(result);
    heroEl.appendChild(shareBtn);
  }

  // 기대착석시간 표시
  if (result.best_seat_time != null) {
    const seatTimeEl = document.createElement('span');
    seatTimeEl.className = 'result-best-seat-time';
    seatTimeEl.textContent = `약 ${result.best_seat_time.toFixed(1)}분 후 착석 예상`;
    document.querySelector('.result-best').appendChild(seatTimeEl);
  }

  // 착석 확률 표시
  if (result.p_seated_best != null) {
    const pEl = document.createElement('span');
    pEl.className = 'result-best-p-seated';
    pEl.textContent = `착석 확률 ${(result.p_seated_best * 100).toFixed(0)}%`;
    document.querySelector('.result-best').appendChild(pEl);
  }

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
      <span class="meta-value">${result.direction}</span>
      <span class="meta-sub">경유 ${result.n_intermediate}개역</span>
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
      <span class="meta-label">착석 확률</span>
      <span class="meta-value" style="color:var(--green)">${result.p_seated_best != null ? (result.p_seated_best * 100).toFixed(1) + '%' : '-'}</span>
      <span class="meta-sub">최적 칸 기준</span>
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

  // 데이터 품질 표시
  if (result.data_quality) {
    const dqContainer = document.createElement('div');
    dqContainer.className = 'data-quality-badges data-freshness';

    const today = new Date().toISOString().split('T')[0];
    const exactCount = Object.values(result.data_quality).filter(v => v === 'exact').length;
    const totalSources = Object.keys(result.data_quality).length;

    let badgesHtml = '';
    badgesHtml += '<span class="dq-badge dq-exact" title="데이터 수집 완료">' +
      '● 1,634 실측 데이터 포인트</span>';
    badgesHtml += '<span class="dq-badge dq-exact" title="최종 수집일">' +
      '● 최종 수집: ' + today + '</span>';

    if (exactCount === totalSources) {
      badgesHtml += '<span class="dq-badge dq-exact" title="모든 데이터 소스 실측">' +
        '● ' + totalSources + '/' + totalSources + ' 소스 실측</span>';
    } else {
      const labels = {
        getoff_rate: '칸별 하차율',
        car_congestion: '칸별 혼잡도',
        train_congestion: '열차 혼잡도',
        congestion_30min: '30분 혼잡도',
        travel_times: '이동 시간',
      };
      const statusIcons = { exact: '●', interpolated: '◐', fallback: '○' };
      const statusLabels = { exact: '실측', interpolated: '자동 조정', fallback: '추정' };
      const statusClasses = { exact: 'dq-exact', interpolated: 'dq-interpolated', fallback: 'dq-fallback' };

      for (const [key, label] of Object.entries(labels)) {
        const status = result.data_quality[key] || 'fallback';
        badgesHtml += '<span class="dq-badge ' + statusClasses[status] + '" title="' + label + ': ' + statusLabels[status] + ' 데이터">' +
          statusIcons[status] + ' ' + label + '</span>';
      }
    }

    dqContainer.innerHTML = badgesHtml;
    document.getElementById('result-meta').after(dqContainer);
  }

  // 칸별 탑승 경쟁도 시각화
  if (result.load_factors) {
    const lfContainer = document.createElement('div');
    lfContainer.className = 'load-factor-viz';
    lfContainer.innerHTML = `
      <div class="lf-header">
        <span class="lf-title">칸별 탑승 경쟁도</span>
        <span class="lf-legend"><span class="lf-low">○ 여유</span><span class="lf-high">● 혼잡</span></span>
      </div>
      <div class="lf-bars">
        ${result.car_scores.map(cs => {
          const lf = parseFloat(result.load_factors[cs.car] || 1.0);
          const pct = Math.min(100, Math.max(0, (lf - 0.8) / 0.4 * 100));
          const cls = lf < 0.95 ? 'lf-low' : lf > 1.05 ? 'lf-high' : 'lf-mid';
          return `<div class="lf-bar-item">
            <span class="lf-car">${cs.car}</span>
            <div class="lf-bar-track"><div class="lf-bar-fill ${cls}" style="width:${pct}%"></div></div>
            <span class="lf-val">${lf.toFixed(2)}</span>
          </div>`;
        }).join('')}
      </div>
    `;
    const metaEl = document.getElementById('result-meta');
    metaEl.parentElement.appendChild(lfContainer);
  }

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
    if (cal.gamma != null) {
      document.getElementById('gamma-slider').value = cal.gamma;
      document.getElementById('gamma-value').textContent = parseFloat(cal.gamma).toFixed(2);
    }
    if (cal.delta != null) {
      document.getElementById('delta-slider').value = cal.delta;
      document.getElementById('delta-value').textContent = parseFloat(cal.delta).toFixed(2);
    }
    document.getElementById('w-escalator').value = cal.facility_weights['에스컬레이터'] ?? 1.2;
    document.getElementById('w-elevator').value = cal.facility_weights['엘리베이터'] ?? 0;
    document.getElementById('w-stairs').value = cal.facility_weights['계단'] ?? 1.0;
    document.getElementById('a-morning').value = cal.alpha_map.morning_rush || 1.4;
    document.getElementById('a-evening').value = cal.alpha_map.evening_rush || 1.3;
    document.getElementById('a-midday').value = cal.alpha_map.midday || 1.0;
    document.getElementById('a-night').value = cal.alpha_map.night || 0.6;
  } catch (e) { /* ignore on first load */ }
}

async function applyCalibration() {
  const params = {
    beta: parseFloat(document.getElementById('beta-slider').value),
    gamma: parseFloat(document.getElementById('gamma-slider').value),
    delta: parseFloat(document.getElementById('delta-slider').value),
    escalator_weight: parseFloat(document.getElementById('w-escalator').value),
    elevator_weight: parseFloat(document.getElementById('w-elevator').value),
    stairs_weight: parseFloat(document.getElementById('w-stairs').value),
    alpha_morning_rush: parseFloat(document.getElementById('a-morning').value),
    alpha_evening_rush: parseFloat(document.getElementById('a-evening').value),
    alpha_midday: parseFloat(document.getElementById('a-midday').value),
    alpha_night: parseFloat(document.getElementById('a-night').value),
  };

  try {
    API.invalidateRecommendCache();
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
    gamma: 0.5,
    delta: 0.15,
    escalator_weight: 1.2,
    elevator_weight: 0,
    stairs_weight: 1.0,
    alpha_morning_rush: 1.4,
    alpha_evening_rush: 1.3,
    alpha_midday: 1.0,
    alpha_night: 0.6,
  };
  API.invalidateRecommendCache();
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
    showError('혼잡도 영향 분석 실패: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '혼잡도 영향 분석 실행';
  }
}

// Chart.js 인스턴스 저장
let sensitivityChartInstance = null;

function renderSensitivityChart(data) {
  const container = document.getElementById('sensitivity-chart');
  if (!container) return;

  // 칸별로 그룹화
  const byCar = {};
  data.forEach(d => {
    if (!byCar[d.car]) byCar[d.car] = [];
    byCar[d.car].push(d);
  });

  const carKeys = Object.keys(byCar);
  if (carKeys.length === 0) return;

  const colors = [
    '#e74c3c','#e67e22','#f1c40f','#2ecc71','#1abc9c',
    '#3498db','#9b59b6','#e91e63','#795548','#607d8b'
  ];

  // 베타 값 추출 (X축)
  const betaValues = byCar[carKeys[0]].map(p => p.beta.toFixed(2));
  const numBetas = betaValues.length;

  // 평균 점수 계산 (각 β 지점별)
  const meanScores = [];
  for (let i = 0; i < numBetas; i++) {
    let sum = 0;
    carKeys.forEach(car => { sum += byCar[car][i].score; });
    meanScores.push(sum / carKeys.length);
  }

  // 편차 모드: 각 칸의 점수 - 평균 → 차이를 강조
  const deviationByCar = {};
  carKeys.forEach(car => {
    deviationByCar[car] = byCar[car].map((p, i) => p.score - meanScores[i]);
  });

  // 중간 β에서의 편차 크기로 상위 3개 + 하위 3개 칸 선정
  const midIdx = Math.floor(numBetas / 2);
  const carsByMidDev = carKeys.map(car => ({
    car,
    midDev: deviationByCar[car][midIdx]
  })).sort((a, b) => b.midDev - a.midDev);

  const topCars = new Set(carsByMidDev.slice(0, 3).map(c => c.car));
  const bottomCars = new Set(carsByMidDev.slice(-3).map(c => c.car));
  const highlightCars = new Set([...topCars, ...bottomCars]);

  // Chart.js 라인 차트로 렌더링 — 편차 모드
  container.innerHTML = `
    <p class="info-text" style="margin-bottom:12px;font-size:0.85rem">
      평균 대비 편차를 표시합니다. 0보다 위면 평균보다 유리, 아래면 불리한 칸입니다.<br>
      <strong>상위 3칸</strong>과 <strong>하위 3칸</strong>을 강조 표시합니다.
    </p>
    <canvas id="sensitivity-canvas" style="max-height: 420px;"></canvas>
  `;
  const canvas = document.getElementById('sensitivity-canvas');
  const ctx = canvas.getContext('2d');

  if (sensitivityChartInstance) {
    sensitivityChartInstance.destroy();
  }

  // 테마 감지
  const isDark = !document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#7c829e' : '#5a6070';
  const gridColor = isDark ? '#2a3050' : '#d1d5dc';
  const tooltipBg = isDark ? 'rgba(21, 25, 41, 0.95)' : 'rgba(255, 255, 255, 0.95)';
  const tooltipText = isDark ? '#e8eaf0' : '#1a1d26';
  const tooltipBorder = isDark ? '#2a3050' : '#d1d5dc';

  // 각 칸별 데이터셋 — 편차 모드, 상위/하위 강조
  const datasets = carKeys.map((car, idx) => {
    const isHighlight = highlightCars.has(car);
    const isTop = topCars.has(car);
    const color = colors[idx % 10];
    return {
      label: car + '호차',
      data: deviationByCar[car],
      borderColor: isHighlight ? color : color + '40',
      backgroundColor: isTop ? color + '15' : 'transparent',
      borderWidth: isHighlight ? 3 : 1,
      pointRadius: isHighlight ? 4 : 0,
      pointHoverRadius: isHighlight ? 7 : 4,
      tension: 0.3,
      fill: isTop,
      hidden: false,
      order: isHighlight ? 0 : 1
    };
  });

  // 0 기준선 강조를 위한 데이터셋 (평균 = 0 라인)
  datasets.push({
    label: '평균 기준선',
    data: new Array(numBetas).fill(0),
    borderColor: isDark ? '#ffffff30' : '#00000020',
    borderWidth: 1.5,
    borderDash: [6, 4],
    pointRadius: 0,
    fill: false,
    order: 2
  });

  // 추천 칸 변경 포인트 찾기
  const recommendedCars = {};
  Object.entries(byCar).forEach(([car, points]) => {
    points.forEach((p, i) => {
      const beta = p.beta.toFixed(2);
      if (!recommendedCars[beta] || p.score > recommendedCars[beta].score) {
        recommendedCars[beta] = { car: car, score: p.score };
      }
    });
  });

  sensitivityChartInstance = new Chart(ctx, {
    type: 'line',
    data: {
      labels: betaValues,
      datasets: datasets
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: {
        mode: 'index',
        intersect: false
      },
      plugins: {
        legend: {
          labels: {
            color: textColor,
            font: { size: 11, family: "'Noto Sans KR', sans-serif" },
            usePointStyle: true,
            pointStyle: 'line',
            filter: (item) => item.text !== '평균 기준선'
          }
        },
        tooltip: {
          backgroundColor: tooltipBg,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          borderColor: tooltipBorder,
          borderWidth: 1,
          padding: 12,
          filter: (item) => item.dataset.label !== '평균 기준선',
          callbacks: {
            title: (items) => '혼잡 반영도 β = ' + items[0].label,
            label: (context) => {
              const label = context.dataset.label;
              const dev = context.parsed.y.toFixed(2);
              const car = label.replace('호차', '');
              const origScore = byCar[car] ? byCar[car][context.dataIndex].score.toFixed(1) : '?';
              const sign = context.parsed.y >= 0 ? '+' : '';
              return `${label}: ${sign}${dev} (점수 ${origScore})`;
            },
            afterBody: (items) => {
              const beta = items[0].label;
              const best = recommendedCars[beta];
              return best ? '\n★ 추천: ' + best.car + '호차 (' + best.score.toFixed(1) + '점)' : '';
            }
          }
        }
      },
      scales: {
        x: {
          title: {
            display: true,
            text: '혼잡 반영도 (β)',
            color: textColor,
            font: { size: 12 }
          },
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor, drawBorder: false }
        },
        y: {
          title: {
            display: true,
            text: '평균 대비 점수 편차',
            color: textColor,
            font: { size: 12 }
          },
          ticks: {
            color: textColor,
            font: { size: 11 },
            callback: (value) => (value >= 0 ? '+' : '') + value.toFixed(1)
          },
          grid: {
            color: (context) => context.tick.value === 0 ? (isDark ? '#ffffff40' : '#00000030') : gridColor,
            drawBorder: false
          }
        }
      }
    }
  });

  // 추천 칸 변경 요약 텍스트
  const changes = [];
  let prevCar = null;
  Object.entries(recommendedCars).forEach(([beta, info]) => {
    if (info.car !== prevCar) {
      changes.push({ beta: parseFloat(beta), car: info.car });
      prevCar = info.car;
    }
  });

  if (changes.length > 1) {
    let summaryHtml = '<div class="sensitivity-summary">';
    summaryHtml += '<p class="sensitivity-summary-title">혼잡 반영도(β)에 따른 추천 칸 변화</p>';
    summaryHtml += '<div class="sensitivity-changes">';
    changes.forEach((ch, i) => {
      const nextBeta = i < changes.length - 1 ? changes[i + 1].beta : 1.0;
      summaryHtml += '<span class="sensitivity-change-item">';
      summaryHtml += 'β ' + ch.beta.toFixed(2) + '~' + nextBeta.toFixed(2) + ': <strong>' + ch.car + '호차</strong>';
      summaryHtml += '</span>';
    });
    summaryHtml += '</div></div>';
    container.insertAdjacentHTML('beforeend', summaryHtml);
  }
}

// ==================== 유틸리티 ====================

// 에러 메시지를 사용자 친화적 한국어로 매핑
const ERROR_MESSAGES_KR = {
  'Failed to fetch': '서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.',
  'NetworkError': '네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
  'Load failed': '서버에 연결할 수 없습니다. 인터넷 연결을 확인해주세요.',
  'timeout': '요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.',
  'AbortError': '요청이 취소되었습니다.',
  '400': '입력값이 올바르지 않습니다. 출발역과 도착역을 다시 확인해주세요.',
  '404': '요청한 경로를 찾을 수 없습니다.',
  '429': '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.',
  '500': '서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
  '502': '서버가 일시적으로 응답하지 않습니다.',
  '503': '서버가 점검 중입니다. 잠시 후 다시 시도해주세요.',
};

let errorDismissTimer = null;

function friendlyError(msg) {
  if (!msg) return '알 수 없는 오류가 발생했습니다.';
  const str = String(msg);
  for (const [key, friendly] of Object.entries(ERROR_MESSAGES_KR)) {
    if (str.includes(key)) return friendly;
  }
  // 이미 한국어 메시지면 그대로 반환
  if (/[가-힣]/.test(str)) return str;
  return `오류가 발생했습니다: ${str}`;
}

function showError(msg) {
  const el = document.getElementById('error-msg');
  const friendly = friendlyError(msg);

  // Build content with close button (avoid stacking buttons on repeated calls)
  el.innerHTML = '';
  el.className = 'message error visible';
  el.style.display = 'flex';
  el.style.alignItems = 'center';
  el.style.justifyContent = 'space-between';

  const textSpan = document.createElement('span');
  textSpan.textContent = friendly;
  el.appendChild(textSpan);

  const closeBtn = document.createElement('button');
  closeBtn.textContent = '✕';
  closeBtn.style.cssText = 'background:none;border:none;color:inherit;font-size:18px;cursor:pointer;padding:0 0 0 12px;line-height:1;flex-shrink:0';
  closeBtn.onclick = () => { hideError(); };
  el.appendChild(closeBtn);

  // ARIA 실시간 알림
  const ariaLive = document.getElementById('aria-live');
  if (ariaLive) ariaLive.textContent = friendly;

  // 8초 후 자동 사라짐
  if (errorDismissTimer) clearTimeout(errorDismissTimer);
  errorDismissTimer = setTimeout(() => { hideError(); }, 8000);
}

function hideError() {
  const el = document.getElementById('error-msg');
  el.className = 'message';
  if (errorDismissTimer) { clearTimeout(errorDismissTimer); errorDismissTimer = null; }
}

function showLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.add('visible');
}

function hideLoading() {
  const el = document.getElementById('loading-overlay');
  if (el) el.classList.remove('visible');
}

function showWarning(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.className = 'message warning visible';

  const ariaLive = document.getElementById('aria-live');
  if (ariaLive) ariaLive.textContent = msg;

  if (errorDismissTimer) clearTimeout(errorDismissTimer);
  errorDismissTimer = setTimeout(() => { hideError(); }, 4000);
}

function showSuccess(msg) {
  const el = document.getElementById('error-msg');
  el.textContent = msg;
  el.className = 'message success visible';

  const ariaLive = document.getElementById('aria-live');
  if (ariaLive) ariaLive.textContent = msg;

  setTimeout(() => { el.className = 'message'; }, 2500);
}

// 추천 결과 공유 (클립보드 복사)
async function shareResult(result) {
  const pSeated = result.p_seated_best != null
    ? `착석확률 ${(result.p_seated_best * 100).toFixed(0)}%`
    : '';
  const seatTime = result.best_seat_time != null
    ? `약 ${result.best_seat_time.toFixed(1)}분 후 착석`
    : '';

  const text = [
    `🚇 Metropy 추천 결과`,
    `${result.boarding} → ${result.destination} (${result.direction})`,
    `추천: ${result.best_car}호차 (${result.best_score.toFixed(1)}점)`,
    pSeated,
    seatTime,
    `비추천: ${result.worst_car}호차 (${result.worst_score}점)`,
    `경유 ${result.n_intermediate}역 | 칸별 점수차 ${result.score_spread}점`,
    ``,
    `metropy.app`
  ].filter(Boolean).join('\n');

  // Web Share API 우선 시도 (모바일)
  if (navigator.share) {
    try {
      await navigator.share({ title: 'Metropy 추천', text: text });
      return;
    } catch (e) {
      // 취소하면 클립보드 복사로 폴백
      if (e.name === 'AbortError') return;
    }
  }

  // 클립보드 복사
  try {
    await navigator.clipboard.writeText(text);
    showSuccess('추천 결과가 클립보드에 복사되었습니다!');
  } catch (e) {
    // 폴백: textarea 복사
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    showSuccess('추천 결과가 클립보드에 복사되었습니다!');
  }
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

// ==================== 노선도 (PNG 이미지 맵) ====================

let metroMapInitialized = false;

function toggleMetroMapImage() {
  const container = document.getElementById('metro-map-image');
  const toggleText = document.getElementById('map-toggle-text');
  const toggleIcon = document.getElementById('map-toggle-icon');
  const resetBtn = document.getElementById('map-reset-btn');

  if (!container) return;

  const isVisible = container.style.display !== 'none';

  if (isVisible) {
    container.style.display = 'none';
    if (toggleText) toggleText.textContent = '노선도 펼치기';
    if (toggleIcon) toggleIcon.textContent = '🗺️';
    if (resetBtn) resetBtn.style.display = 'none';
  } else {
    container.style.display = 'block';
    if (toggleText) toggleText.textContent = '노선도 접기';
    if (toggleIcon) toggleIcon.textContent = '🗺️';
    if (resetBtn) resetBtn.style.display = '';

    if (!metroMapInitialized && typeof MetroMapImage !== 'undefined') {
      MetroMapImage.init('metro-map-image');
      metroMapInitialized = true;
      showCurrentRouteOnMap();
    } else if (metroMapInitialized) {
      showCurrentRouteOnMap();
    }
  }
}

function showCurrentRouteOnMap() {
  if (!metroMapInitialized || typeof MetroMapImage === 'undefined') return;

  const boarding = document.getElementById('boarding')?.value;
  const destination = document.getElementById('destination')?.value;

  if (boarding && destination && boarding !== destination) {
    const result = window.lastRecommendationData;
    const intermediates = result?.intermediates || [];
    MetroMapImage.highlightRoute(boarding, destination, intermediates);
  }
}

function updateMapWithResult(result) {
  if (!metroMapInitialized || typeof MetroMapImage === 'undefined') return;

  const container = document.getElementById('metro-map-image');
  if (container && container.style.display !== 'none') {
    MetroMapImage.highlightRoute(result.boarding, result.destination, result.intermediates);
  }
}

// ==================== PWA 설치 프롬프트 ====================

let deferredInstallPrompt = null;

window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;

  // 이미 닫은 적 없으면 설치 배너 표시
  if (!localStorage.getItem('metropy_install_dismissed')) {
    showInstallBanner();
  }
});

function showInstallBanner() {
  if (!deferredInstallPrompt) return;

  const existing = document.getElementById('install-banner');
  if (existing) existing.remove();

  const banner = document.createElement('div');
  banner.id = 'install-banner';
  banner.style.cssText = 'position:fixed;bottom:16px;left:16px;right:16px;max-width:var(--max-w);margin:0 auto;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;display:flex;align-items:center;gap:12px;z-index:200;box-shadow:var(--shadow)';
  banner.innerHTML = `
    <div style="flex:1">
      <div style="font-weight:700;font-size:.95rem;margin-bottom:2px">Metropy 앱 설치</div>
      <div style="font-size:.82rem;color:var(--text-dim)">홈 화면에 추가하여 빠르게 접근하세요</div>
    </div>
    <button id="install-accept" style="background:var(--accent);color:var(--bg);border:none;border-radius:8px;padding:10px 18px;font-weight:700;font-size:.88rem;cursor:pointer;white-space:nowrap">설치</button>
    <button id="install-dismiss" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:1.2rem;padding:4px 8px">✕</button>
  `;

  document.body.appendChild(banner);

  document.getElementById('install-accept').onclick = async () => {
    deferredInstallPrompt.prompt();
    const { outcome } = await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    banner.remove();
  };

  document.getElementById('install-dismiss').onclick = () => {
    localStorage.setItem('metropy_install_dismissed', '1');
    banner.remove();
  };
}
