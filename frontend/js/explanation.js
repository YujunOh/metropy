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
              <span class="score-label">착석 기회</span>
              <span class="score-value benefit-text">+${normalizedData.normBenefit.toFixed(1)}</span>
            </div>
            <div class="score-item penalty">
              <span class="score-label">혼잡 감점</span>
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

        <!-- 착석 확률 분석 (v4) -->
        ${carData.p_seated != null ? `
        <div class="explanation-section">
          <h4>착석 확률 분석</h4>
          <div class="v4-prob-section">
            <div class="prob-main">
              <span class="prob-value">${(carData.p_seated * 100).toFixed(1)}%</span>
              <span class="prob-label">도착 전 착석 확률</span>
            </div>
            <div class="prob-bar">
              <div class="prob-bar-fill" style="width:${Math.min(100, carData.p_seated * 100)}%"></div>
            </div>
            <p class="info-text" style="margin-top:8px">
              이 칸에 탑승했을 때, 도착 전에 앉을 수 있는 확률입니다. 경유역에서 자리가 비는 패턴과 같은 칸 대기 인원을 종합하여 계산합니다.
            </p>
          </div>
        </div>
        ` : ''}

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

        <!-- 전략 팁 -->
        <div class="explanation-section">
          <h4>💡 착석 전략 팁</h4>
          <div class="strategy-tips">
            ${this.generateStrategyTips(carData.car)}
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
      // 실제 API 기반 station contribution 데이터 사용 (v4 필드 포함)
      const carContribs = contribs[String(carNum)];
      stationData = carContribs
        .filter(c => c.contribution > 0)
        .sort((a, b) => b.contribution - a.contribution)
        .slice(0, 7)
        .map(c => {
          const lEff = c.L_eff != null ? c.L_eff : (c.L || 1.0);
          const cAdj = c.C_adj != null ? c.C_adj : (c.C || 0);
          return {
            name: c.station,
            contribution: c.contribution,
            detail: `빈 자리 ${(c.A || 0).toFixed(1)}석, 대기 인원 ${(c.C || 0).toFixed(0)}→${cAdj.toFixed(0)}명(보정), 경쟁도 ${lEff.toFixed(2)}, 차지 확률 ${((c.p_capture || 0) * 100).toFixed(1)}%`,
            p_capture: c.p_capture || 0,
            p_first: c.p_first || 0,
            A: c.A || 0,
            C: c.C || 0,
            L_eff: lEff,
            C_adj: cAdj
          };
        });
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
      const capturePct = station.p_capture != null ? (station.p_capture * 100).toFixed(1) : null;
      return `
        <div class="contribution-bar-wrapper" title="${station.detail}">
          <span class="contribution-station">${station.name}</span>
          <div class="contribution-bar-container">
            <div class="contribution-bar" style="width: ${width}%"></div>
          </div>
          <span class="contribution-value">${station.contribution > 100 ? station.contribution.toFixed(0) : station.contribution.toFixed(1)}</span>
          ${capturePct != null ? `<span class="contribution-capture">${capturePct}%</span>` : ''}
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

  // 시설 효과 설명 — 프로젝트 핵심 가치(빠른하차 회피, 문 위치 전략, 에스컬레이터 회피) 반영
  describeFacilityBenefit(carNum) {
    if (carNum <= 2 || carNum >= 9) {
      return '에스컬레이터·계단에서 먼 칸으로, 네이버 "빠른하차" 추천을 피해 탑승 경쟁이 적고 혼잡도가 낮은';
    } else if (carNum >= 4 && carNum <= 7) {
      return '출입문(x-2, x-3 위치)이 양쪽 일반석에 모두 가까워 빈 자리를 양방향으로 노릴 수 있는';
    } else {
      return '에스컬레이터에서 적당히 떨어져 있어 탑승 경쟁과 착석 기회가 균형 잡힌';
    }
  }

  // 요약 생성 — 프로젝트 핵심 가치(빠른하차 회피, 문 위치 전략, 에스컬레이터 회피) 반영
  generateSummary(carData, routeData) {
    const rank = carData.rank || '?';
    const car = carData.car;
    const intermediates = routeData.intermediates || [];

    // station_contributions에서 가장 기여가 큰 역 찾기
    let topStation = '';
    const contribs = routeData.station_contributions;
    if (contribs && contribs[String(car)]) {
      const carContribs = contribs[String(car)];
      const sorted = [...carContribs].sort((a, b) => b.contribution - a.contribution);
      if (sorted.length > 0) {
        topStation = sorted[0].station;
      }
    }

    const stationHint = topStation
      ? ` ${topStation}역에서 하차가 많아 빈 자리가 생길 가능성이 높습니다.`
      : intermediates.length > 2
        ? ` ${intermediates.length}개 경유역의 하차 패턴이 반영되었습니다.`
        : '';

    const pSeatedHint = carData.p_seated != null
      ? ` 착석 확률 약 ${(carData.p_seated * 100).toFixed(0)}%.`
      : '';

    // 칸 위치에 따른 전략 팁
    let strategyHint = '';
    if (car <= 2 || car >= 9) {
      strategyHint = ' 에스컬레이터·계단에서 먼 칸이라 "빠른하차" 승객이 적고, 줄이 짧아 빠르게 탑승 후 한쪽 일반석을 노릴 수 있습니다.';
    } else if (car >= 4 && car <= 7) {
      strategyHint = ' 출입문 기준 양쪽 일반석에 모두 가까워 빈 자리를 양방향으로 확인할 수 있는 위치입니다.';
    }

    if (rank === 1) {
      return `이 경로에서 앉을 확률이 가장 높은 칸입니다.${pSeatedHint}${strategyHint}${stationHint}`;
    } else if (rank <= 3) {
      return `${rank}위 추천 칸입니다.${pSeatedHint}${strategyHint}${stationHint}`;
    } else if (rank >= 8) {
      return `${rank}위로 하위권입니다. 에스컬레이터·계단 근처라 탑승 경쟁이 치열하거나, 중간역 하차가 적어 빈 자리가 잘 안 납니다.`;
    } else {
      return `${rank}위로 중간 수준입니다.${pSeatedHint}${stationHint}`;
    }
  }

  // 착석 전략 팁 생성 — 빠른하차 회피, 문 위치, 에스컬레이터 회피 전략 설명
  generateStrategyTips(carNum) {
    const tips = [];

    // 공통 팁
    tips.push('<p class="info-text"><strong>기본 원리:</strong> 네이버 지도의 "빠른하차" 추천 위치를 피하면, 같은 칸 탑승 경쟁이 줄어들어 착석 확률이 올라갑니다.</p>');

    if (carNum <= 2 || carNum >= 9) {
      tips.push('<p class="info-text strategy-good"><strong>✓ 에스컬레이터 회피 전략:</strong> 이 칸은 계단·에스컬레이터에서 먼 위치입니다. 대부분의 승객이 출구와 가까운 중앙 칸으로 몰리므로, 이 칸은 줄이 짧아 빠르게 탑승할 수 있습니다.</p>');
      tips.push('<p class="info-text strategy-good"><strong>✓ 빠른 탑승 후 일반석 노리기:</strong> 줄이 짧은 끝 칸(x-1, x-4 위치)에 빠르게 탑승하여, 노약자석이 아닌 한쪽 일반석을 집중적으로 노리는 전략입니다.</p>');
    } else if (carNum >= 4 && carNum <= 7) {
      tips.push('<p class="info-text strategy-good"><strong>✓ 양방향 좌석 전략:</strong> 출입문(x-2, x-3 위치) 기준으로 양쪽 일반석이 모두 보이는 위치입니다. 한쪽이 만석이어도 반대쪽에서 빈 자리를 찾을 수 있습니다.</p>');
      tips.push('<p class="info-text strategy-caution"><strong>⚠ 주의:</strong> 다만 에스컬레이터·계단 근처 칸이라 탑승 대기 경쟁이 치열할 수 있습니다. 점수에 이미 반영되어 있습니다.</p>');
    } else {
      tips.push('<p class="info-text"><strong>균형 위치:</strong> 에스컬레이터에서 적당히 떨어져 탑승 경쟁과 착석 기회가 균형 잡힌 칸입니다.</p>');
    }

    return tips.join('');
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
      morning: { range: [7, 9], name: '출근 시간대', multiplier: 1.4 },
      evening: { range: [18, 20], name: '퇴근 시간대', multiplier: 1.3 },
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
