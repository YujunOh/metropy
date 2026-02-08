// 추천 이유 시각화 모듈
class RecommendationExplainer {
  constructor() {
    this.currentExplanation = null;
  }

  // 추천 이유 시각화
  showExplanation(carData, routeData, containerId = 'car-detail') {
    const container = document.getElementById(containerId);
    if (!container) return;

    this.currentExplanation = { carData, routeData };

    // Normalize benefit/penalty to match total score scale
    const allCars = routeData.car_scores || [];
    const normalizedData = this.normalizeScores(carData, allCars);

    // 메인 설명 HTML
    const html = `
      <div class="explanation-container">
        <div class="explanation-header">
          <h3>${carData.car}호차 추천 이유</h3>
          <button class="icon-btn" onclick="explainer.hideExplanation()">✕</button>
        </div>

        <!-- 점수 분해 (정규화된 값) -->
        <div class="explanation-section">
          <h4>점수 구성</h4>
          <div class="score-breakdown">
            <div class="score-item benefit">
              <span class="score-label">착석 기회 (Benefit)</span>
              <span class="score-value benefit-text">+${normalizedData.normBenefit.toFixed(1)}</span>
            </div>
            <div class="score-item penalty">
              <span class="score-label">탑승 혼잡 감점 (Penalty)</span>
              <span class="score-value penalty-text">-${normalizedData.normPenalty.toFixed(1)}</span>
            </div>
            <div class="score-item total">
              <span class="score-label">최종 점수</span>
              <span class="score-value">${carData.score.toFixed(1)}점</span>
            </div>
          </div>
          <div class="score-ratio-bar">
            <div class="score-ratio-benefit" style="width:${normalizedData.benefitPct}%"></div>
            <div class="score-ratio-penalty" style="width:${normalizedData.penaltyPct}%"></div>
          </div>
          <div class="score-ratio-labels">
            <span class="benefit-text">착석 기회 ${normalizedData.benefitPct.toFixed(0)}%</span>
            <span class="penalty-text">혼잡 감점 ${normalizedData.penaltyPct.toFixed(0)}%</span>
          </div>
        </div>

        <!-- 중간역 하차 기여 -->
        <div class="explanation-section">
          <h4>경유역 하차 기여</h4>
          <p class="info-text" style="margin-bottom:12px">경유역에서 승객이 많이 내릴수록 빈 자리가 생겨 착석 기회가 높아집니다.</p>
          <div id="station-contribution-${carData.car}"></div>
        </div>

        <!-- 시설 가중치 효과 -->
        <div class="explanation-section">
          <h4>시설 위치 효과</h4>
          <div class="facility-info">
            <p class="info-text">
              이 칸은 <strong>${this.describeFacilityPosition(carData.car)}</strong> 위치하여,
              ${this.describeFacilityBenefit(carData.car)} 효과가 있습니다.
            </p>
          </div>
        </div>

        <!-- 추천 이유 요약 -->
        <div class="explanation-section">
          <h4>한 줄 요약</h4>
          <p class="summary-text">${this.generateSummary(carData, routeData)}</p>
        </div>
      </div>
    `;

    container.innerHTML = html;
    container.style.display = 'block';

    // 중간역 기여도 렌더링 (실제 API 데이터 활용)
    this.renderStationContribution(carData.car, routeData);
  }

  // Benefit/Penalty를 Total Score 스케일로 정규화
  normalizeScores(carData, allCars) {
    const rawBenefit = carData.benefit;
    const rawPenalty = carData.penalty;
    const totalRaw = rawBenefit + rawPenalty;

    // Benefit과 Penalty 비율 (원본 기준)
    const benefitPct = totalRaw > 0 ? (rawBenefit / totalRaw) * 100 : 50;
    const penaltyPct = totalRaw > 0 ? (rawPenalty / totalRaw) * 100 : 50;

    // Total Score 기준으로 정규화된 값 산출
    // score = normalized(benefit - beta*penalty) → 역산 근사
    const allScores = allCars.map(c => c.score);
    const maxScore = allScores.length > 0 ? Math.max(...allScores) : 100;
    const minScore = allScores.length > 0 ? Math.min(...allScores) : 0;
    const scoreRange = maxScore - minScore || 1;

    // 정규화: benefit의 비례 기여분과 penalty 기여분
    const rawNet = rawBenefit - rawPenalty;
    const allBenefits = allCars.map(c => c.benefit);
    const allPenalties = allCars.map(c => c.penalty);
    const maxRawNet = allCars.length > 0
      ? Math.max(...allCars.map(c => c.benefit - c.penalty))
      : rawNet;
    const minRawNet = allCars.length > 0
      ? Math.min(...allCars.map(c => c.benefit - c.penalty))
      : rawNet;
    const rawRange = maxRawNet - minRawNet || 1;

    // 비례 정규화
    const normFactor = scoreRange / rawRange;
    const normBenefit = rawBenefit * normFactor;
    const normPenalty = rawPenalty * normFactor;

    return { normBenefit, normPenalty, benefitPct, penaltyPct };
  }

  // 중간역 기여도 렌더링 (API 실데이터 활용)
  renderStationContribution(carNum, routeData) {
    const containerId = `station-contribution-${carNum}`;
    const container = document.getElementById(containerId);
    if (!container) return;

    // station_contributions가 있으면 실데이터 사용
    const contribs = routeData.station_contributions;
    const intermediates = routeData.intermediates || [];

    if (intermediates.length === 0) {
      container.innerHTML = '<p class="info-text">직통 경로입니다 (중간역 없음)</p>';
      return;
    }

    let stationData = [];

    if (contribs && contribs[String(carNum)]) {
      // 실제 API 기반 station contribution 데이터 사용
      const carContribs = contribs[String(carNum)];
      stationData = carContribs
        .filter(c => c.contribution > 0)
        .sort((a, b) => b.contribution - a.contribution)
        .slice(0, 7)
        .map(c => ({
          name: c.station,
          contribution: c.contribution,
          detail: `하차량 D=${c.D.toFixed(0)}, 잔여시간 T=${c.T.toFixed(0)}s`
        }));
    } else {
      // 폴백: 중간역 이름 + 근사 기여도 (도착역에 가까울수록 일찍 빈자리)
      stationData = intermediates
        .map((station, idx) => ({
          name: station,
          contribution: (intermediates.length - idx) * 3,
          detail: `도착역까지 ${intermediates.length - idx}역`
        }))
        .slice(0, 7);
    }

    if (stationData.length === 0) {
      container.innerHTML = '<p class="info-text">기여 데이터가 없습니다</p>';
      return;
    }

    const maxContribution = Math.max(...stationData.map(s => s.contribution));

    const barsHTML = stationData.map(station => {
      const width = maxContribution > 0 ? (station.contribution / maxContribution) * 100 : 0;
      return `
        <div class="contribution-bar-wrapper" title="${station.detail}">
          <span class="contribution-station">${station.name}</span>
          <div class="contribution-bar-container">
            <div class="contribution-bar" style="width: ${width}%"></div>
          </div>
          <span class="contribution-value">${station.contribution > 100 ? station.contribution.toFixed(0) : station.contribution.toFixed(1)}</span>
        </div>
      `;
    }).join('');

    const totalStations = intermediates.length;
    const showing = stationData.length;
    const moreText = totalStations > 7
      ? `<p class="info-text" style="margin-top:8px;font-size:0.82rem">총 ${totalStations}개 경유역 중 상위 ${showing}개 표시</p>`
      : '';

    container.innerHTML = `
      <div class="contribution-chart">${barsHTML}</div>
      ${moreText}
    `;
  }

  // 시설 위치 설명
  describeFacilityPosition(carNum) {
    if (carNum <= 2 || carNum >= 9) {
      return '양 끝 칸에';
    } else if (carNum >= 4 && carNum <= 7) {
      return '중앙 칸에';
    } else {
      return '중앙 근처에';
    }
  }

  // 시설 효과 설명
  describeFacilityBenefit(carNum) {
    if (carNum <= 2 || carNum >= 9) {
      return '하차 인원이 적고 탑승 시 혼잡도도 낮은';
    } else if (carNum >= 4 && carNum <= 7) {
      return '에스컬레이터/계단 근처 하차가 많아 자리가 빨리 나는';
    } else {
      return '적당한 하차량과 탑승 편의성을 갖춘';
    }
  }

  // 요약 생성 (중간역 정보 포함)
  generateSummary(carData, routeData) {
    const rank = carData.rank || '?';
    const score = carData.score.toFixed(1);
    const intermediates = routeData.intermediates || [];

    // station_contributions에서 가장 기여가 큰 역 찾기
    let topStation = '';
    const contribs = routeData.station_contributions;
    if (contribs && contribs[String(carData.car)]) {
      const carContribs = contribs[String(carData.car)];
      const sorted = [...carContribs].sort((a, b) => b.contribution - a.contribution);
      if (sorted.length > 0) {
        topStation = sorted[0].station;
      }
    }

    const stationHint = topStation
      ? ` 특히 ${topStation}역에서의 하차가 크게 기여합니다.`
      : intermediates.length > 2
        ? ` ${intermediates.length}개 경유역의 하차 패턴이 반영되었습니다.`
        : '';

    if (rank === 1) {
      return `이 경로에서 착석 효용이 가장 높은 칸입니다.${stationHint}`;
    } else if (rank <= 3) {
      return `${rank}위로 추천되는 칸입니다. 점수 ${score}점으로 착석 기회가 양호합니다.${stationHint}`;
    } else if (rank >= 8) {
      return `${rank}위로 하위권입니다. 탑승 혼잡도가 높거나 중간역 하차가 적어 착석이 어려울 수 있습니다.`;
    } else {
      return `${rank}위로 중간 수준의 착석 기회를 제공합니다.${stationHint}`;
    }
  }

  // 설명 닫기
  hideExplanation() {
    const container = document.getElementById('car-detail');
    if (container) {
      container.style.display = 'none';
      container.innerHTML = '';
    }
    this.currentExplanation = null;
  }

  // 비교 모드
  compareCards(carsData, containerId = 'comparison-view') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const html = `
      <div class="comparison-container">
        <h3>칸별 비교</h3>
        <div class="comparison-grid">
          ${carsData.map(car => `
            <div class="comparison-card">
              <div class="comparison-car-num">${car.car}호차</div>
              <div class="comparison-score">${car.score.toFixed(1)}</div>
              <div class="comparison-breakdown">
                <span class="mini-benefit">+${car.benefit.toFixed(1)}</span>
                <span class="mini-penalty">-${car.penalty.toFixed(1)}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

    container.innerHTML = html;
  }

  // 시간대별 변화 설명
  explainTimeEffect(hour) {
    const periods = {
      morning: { range: [7, 9], name: '출근 러시', multiplier: 1.4 },
      evening: { range: [18, 20], name: '퇴근 러시', multiplier: 1.3 },
      midday: { range: [10, 17], name: '주간', multiplier: 1.0 },
      night: { range: [22, 6], name: '심야', multiplier: 0.6 }
    };

    let currentPeriod = null;
    for (const [key, period] of Object.entries(periods)) {
      const [start, end] = period.range;
      if ((start <= end && hour >= start && hour < end) ||
          (start > end && (hour >= start || hour < end))) {
        currentPeriod = period;
        break;
      }
    }

    if (!currentPeriod) {
      currentPeriod = periods.midday;
    }

    return {
      period: currentPeriod.name,
      multiplier: currentPeriod.multiplier,
      description: `현재 시간대(${hour}시)는 ${currentPeriod.name}으로, 하차량 가중치가 ${currentPeriod.multiplier}배 적용됩니다.`
    };
  }
}

// 전역 인스턴스
const explainer = new RecommendationExplainer();

// 칸 클릭 시 설명 표시
function showCarExplanation(carData, routeData) {
  explainer.showExplanation(carData, routeData);

  const container = document.getElementById('car-detail');
  if (container) {
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}
