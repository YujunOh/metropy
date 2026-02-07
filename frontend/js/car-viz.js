// 열차 칸 시각화 모듈
function scoreToColor(score, min, max) {
  const ratio = max === min ? 0.5 : (score - min) / (max - min);
  // 빨강(0) → 노랑(60) → 초록(120)
  const hue = ratio * 120;
  return `hsl(${hue}, 72%, 45%)`;
}

function scoreToTextColor(score, min, max) {
  const ratio = max === min ? 0.5 : (score - min) / (max - min);
  return ratio > 0.5 ? '#fff' : '#fff';
}

function renderTrain(carScores, containerId = 'train-viz') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const sorted = [...carScores].sort((a, b) => a.car - b.car);
  const scores = sorted.map(c => c.score);
  const minS = Math.min(...scores);
  const maxS = Math.max(...scores);

  container.innerHTML = '';

  // 열차 전체 래퍼
  const train = document.createElement('div');
  train.className = 'train';

  sorted.forEach(car => {
    const el = document.createElement('div');
    el.className = 'car-block';
    if (car.rank === 1) el.classList.add('car-best');
    if (car.rank === sorted.length) el.classList.add('car-worst');

    el.style.backgroundColor = scoreToColor(car.score, minS, maxS);
    el.style.color = scoreToTextColor(car.score, minS, maxS);

    el.innerHTML = `
      <div class="car-number">${car.car}호차</div>
      <div class="car-score">${car.score.toFixed(1)}</div>
      <div class="car-rank">${car.rank}위</div>
    `;

    // 클릭 시 상세 정보 (새로운 설명 UI 사용)
    el.addEventListener('click', () => {
      // 전역 routeData가 있으면 함께 전달
      const routeData = window.lastRecommendationData || {};
      showCarExplanation(car, routeData);
    });
    train.appendChild(el);
  });

  container.appendChild(train);
}

// 레거시 호환성 유지 (기존 showCarDetail 함수)
function showCarDetail(car) {
  const detail = document.getElementById('car-detail');
  if (!detail) return;
  detail.innerHTML = `
    <h3>${car.car}호차 상세</h3>
    <div class="detail-row">
      <span class="detail-label">점수</span>
      <span class="detail-value">${car.score.toFixed(1)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">순위</span>
      <span class="detail-value">${car.rank}위</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Benefit (착석 기회)</span>
      <span class="detail-value benefit">${car.benefit.toFixed(1)}</span>
    </div>
    <div class="detail-row">
      <span class="detail-label">Penalty (탑승 혼잡)</span>
      <span class="detail-value penalty">${car.penalty.toFixed(1)}</span>
    </div>
    <div class="detail-bar">
      <div class="bar-benefit" style="width:${barWidth(car.benefit, car.benefit + car.penalty)}%"></div>
      <div class="bar-penalty" style="width:${barWidth(car.penalty, car.benefit + car.penalty)}%"></div>
    </div>
    <div class="bar-labels">
      <span class="benefit">Benefit</span>
      <span class="penalty">Penalty</span>
    </div>
  `;
  detail.classList.add('visible');
}

function barWidth(value, total) {
  if (total === 0) return 50;
  return (value / total) * 100;
}

// Chart.js 인스턴스 저장
let bpChartInstance = null;
let scoreChartInstance = null;

function renderBenefitPenaltyChart(carScores, containerId = 'bp-chart') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const sorted = [...carScores].sort((a, b) => a.car - b.car);

  // Chart.js 사용
  container.innerHTML = `
    <h2 class="card-title">Benefit vs Penalty 분석</h2>
    <p class="card-desc">각 칸의 착석 기회(Benefit)와 탑승 혼잡(Penalty)을 비교합니다</p>
    <canvas id="bp-canvas" style="max-height: 400px;"></canvas>
  `;

  const canvas = document.getElementById('bp-canvas');
  const ctx = canvas.getContext('2d');

  // 기존 차트가 있으면 제거
  if (bpChartInstance) {
    bpChartInstance.destroy();
  }

  bpChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(c => `${c.car}호차`),
      datasets: [
        {
          label: 'Benefit (착석 기회)',
          data: sorted.map(c => c.benefit),
          backgroundColor: 'rgba(52, 211, 153, 0.8)',
          borderColor: 'rgba(52, 211, 153, 1)',
          borderWidth: 1
        },
        {
          label: 'Penalty (탑승 혼잡)',
          data: sorted.map(c => c.penalty),
          backgroundColor: 'rgba(248, 113, 113, 0.8)',
          borderColor: 'rgba(248, 113, 113, 1)',
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          labels: {
            color: '#e8eaf0',
            font: { size: 12, family: "'Noto Sans KR', sans-serif" }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(21, 25, 41, 0.95)',
          titleColor: '#e8eaf0',
          bodyColor: '#e8eaf0',
          borderColor: '#2a3050',
          borderWidth: 1,
          padding: 12,
          displayColors: true
        }
      },
      scales: {
        x: {
          ticks: { color: '#7c829e', font: { size: 11 } },
          grid: { color: '#2a3050', drawBorder: false }
        },
        y: {
          ticks: { color: '#7c829e', font: { size: 11 } },
          grid: { color: '#2a3050', drawBorder: false }
        }
      }
    }
  });
}

function renderScoreDistributionChart(carScores, containerId = 'score-chart') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const sorted = [...carScores].sort((a, b) => b.score - a.score);

  container.innerHTML = `
    <h2 class="card-title">칸별 SeatScore 분포</h2>
    <p class="card-desc">점수가 높을수록 착석 효용이 높습니다</p>
    <canvas id="score-canvas" style="max-height: 300px;"></canvas>
  `;

  const canvas = document.getElementById('score-canvas');
  const ctx = canvas.getContext('2d');

  if (scoreChartInstance) {
    scoreChartInstance.destroy();
  }

  scoreChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(c => `${c.car}호차`),
      datasets: [{
        label: 'SeatScore',
        data: sorted.map(c => c.score),
        backgroundColor: sorted.map((c, i) => {
          if (i === 0) return 'rgba(52, 211, 153, 0.9)';
          if (i === sorted.length - 1) return 'rgba(248, 113, 113, 0.9)';
          return 'rgba(91, 140, 255, 0.7)';
        }),
        borderColor: sorted.map((c, i) => {
          if (i === 0) return 'rgba(52, 211, 153, 1)';
          if (i === sorted.length - 1) return 'rgba(248, 113, 113, 1)';
          return 'rgba(91, 140, 255, 1)';
        }),
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: 'rgba(21, 25, 41, 0.95)',
          titleColor: '#e8eaf0',
          bodyColor: '#e8eaf0',
          borderColor: '#2a3050',
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (context) => {
              const car = sorted[context.dataIndex];
              return [
                `점수: ${car.score.toFixed(1)}`,
                `순위: ${car.rank}위`,
                `Benefit: ${car.benefit.toFixed(1)}`,
                `Penalty: ${car.penalty.toFixed(1)}`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: '#7c829e', font: { size: 11 } },
          grid: { color: '#2a3050', drawBorder: false }
        },
        y: {
          ticks: { color: '#7c829e', font: { size: 11 } },
          grid: { color: '#2a3050', drawBorder: false },
          beginAtZero: false
        }
      }
    }
  });
}
