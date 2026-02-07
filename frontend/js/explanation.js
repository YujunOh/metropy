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

    // 메인 설명 HTML
    const html = `
      <div class="explanation-container">
        <div class="explanation-header">
          <h3>🎯 ${carData.car}호차 추천 이유</h3>
          <button class="icon-btn" onclick="explainer.hideExplanation()">✕</button>
        </div>

        <!-- 점수 분해 -->
        <div class="explanation-section">
          <h4>📊 점수 구성</h4>
          <div class="score-breakdown">
            <div class="score-item benefit">
              <span class="score-label">Benefit (착석 기회)</span>
              <span class="score-value">+${carData.benefit.toFixed(1)}</span>
            </div>
            <div class="score-item penalty">
              <span class="score-label">Penalty (탑승 혼잡)</span>
              <span class="score-value">-${carData.penalty.toFixed(1)}</span>
            </div>
            <div class="score-item total">
              <span class="score-label">Total Score</span>
              <span class="score-value">${carData.score.toFixed(1)}</span>
            </div>
          </div>
        </div>

        <!-- 중간역 기여도 -->
        <div class="explanation-section">
          <h4>🚉 중간역별 기여도 (Top 5)</h4>
          <div id="station-contribution-${carData.car}"></div>
        </div>

        <!-- 시설 가중치 효과 -->
        <div class="explanation-section">
          <h4>🏗️ 시설 가중치 효과</h4>
          <div class="facility-info">
            <p class="info-text">
              이 칸은 <strong>${this.describeFacilityPosition(carData.car)}</strong> 위치하여,
              ${this.describeFacilityBenefit(carData.car)} 효과가 있습니다.
            </p>
          </div>
        </div>

        <!-- 추천 이유 요약 -->
        <div class="explanation-section">
          <h4>💡 한 줄 요약</h4>
          <p class="summary-text">${this.generateSummary(carData)}</p>
        </div>
      </div>
    `;

    container.innerHTML = html;
    container.style.display = 'block';

    // 중간역 기여도 차트 렌더링
    if (routeData && routeData.intermediate_stations) {
      this.renderStationContribution(carData.car, routeData);
    }
  }

  // 중간역 기여도 차트
  renderStationContribution(carNum, routeData) {
    const containerId = `station-contribution-${carNum}`;
    const container = document.getElementById(containerId);
    if (!container) return;

    // 실제 API 응답에서 중간역 데이터 추출
    const stations = routeData.intermediates || [];

    if (stations.length === 0) {
      container.innerHTML = '<p class="info-text">직통 경로입니다 (중간역 없음)</p>';
      return;
    }

    // TODO: 백엔드에서 칸별/역별 기여도 데이터를 제공하도록 개선 필요
    // 현재는 간단한 근사값 사용: 거리에 따른 가중치 (먼 역일수록 기여도 높음)
    const contributions = stations.map((station, idx) => {
      // 역 순서를 반대로 (도착역에 가까울수록 기여도 높음)
      const positionWeight = stations.length - idx;
      const baseContribution = positionWeight * 3;
      return {
        name: station,
        contribution: baseContribution
      };
    });

    // 모든 역 또는 Top 5만 표시 (역이 5개 이하면 전체 표시)
    const displayStations = contributions.length > 5
      ? contributions.slice(0, 5)
      : contributions;

    // 바 차트 HTML
    const maxContribution = Math.max(...displayStations.map(s => s.contribution));
    const barsHTML = displayStations.map(station => {
      const width = (station.contribution / maxContribution) * 100;
      return `
        <div class="contribution-bar-wrapper">
          <span class="contribution-station">${station.name}</span>
          <div class="contribution-bar-container">
            <div class="contribution-bar" style="width: ${width}%"></div>
          </div>
          <span class="contribution-value">하차 기회</span>
        </div>
      `;
    }).join('');

    const totalStations = stations.length;
    const showing = displayStations.length;
    const moreText = totalStations > 5 ? `<p class="info-text" style="margin-top:8px;font-size:0.85rem">총 ${totalStations}개 역 중 상위 ${showing}개 표시</p>` : '';

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

  // 요약 생성
  generateSummary(carData) {
    const rank = carData.rank || '?';
    const score = carData.score.toFixed(1);
    const benefitRatio = (carData.benefit / (carData.benefit + carData.penalty)) * 100;

    if (rank === 1) {
      return `이 경로에서 착석 효용이 가장 높은 칸입니다. Benefit 비율 ${benefitRatio.toFixed(0)}%로 중간역 하차 패턴이 유리합니다.`;
    } else if (rank <= 3) {
      return `${rank}위로 추천되는 칸입니다. 점수 ${score}점으로 착석 기회가 양호합니다.`;
    } else if (rank >= 8) {
      return `${rank}위로 하위권입니다. 탑승 혼잡도가 높거나 중간역 하차가 적어 착석이 어려울 수 있습니다.`;
    } else {
      return `${rank}위로 중간 수준의 착석 기회를 제공합니다.`;
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

  // 비교 모드: 여러 칸 비교
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

// 칸 클릭 시 설명 표시 (기존 renderTrain에 통합 가능)
function showCarExplanation(carData, routeData) {
  explainer.showExplanation(carData, routeData);

  // 스크롤 이동
  const container = document.getElementById('car-detail');
  if (container) {
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}
