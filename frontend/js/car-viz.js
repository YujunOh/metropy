// 열차 칸 시각화 모듈
function scoreToColor(score, min, max) {
  const ratio = max === min ? 0.5 : (score - min) / (max - min);
  // 빨강(0) → 노랑(60) → 초록(120)
  const hue = ratio * 120;
  return `hsl(${hue}, 72%, 45%)`;
}

function scoreToTextColor(score, min, max) {
  return '#fff';
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
    el.setAttribute('tabindex', '0');
    el.setAttribute('role', 'button');
    el.setAttribute('aria-label', `${car.rank}위 ${car.car}호차 (점수 ${car.score.toFixed(1)})`);
    if (car.rank === 1) el.classList.add('car-best');
    if (car.rank === sorted.length) el.classList.add('car-worst');

    el.style.backgroundColor = scoreToColor(car.score, minS, maxS);
    el.style.color = scoreToTextColor(car.score, minS, maxS);

    const seatTimeHtml = car.estimated_seat_minutes != null
      ? `<div class="car-seat-time">${car.estimated_seat_minutes.toFixed(1)}분</div>`
      : '';

    el.innerHTML = `
      <div class="car-number">${car.car}호차</div>
      <div class="car-score">${car.score.toFixed(1)}</div>
      ${seatTimeHtml}
      <div class="car-rank">${car.rank}위</div>
    `;

    const openCarDetail = () => {
      if (typeof touchHandler !== 'undefined') touchHandler.vibrate([10]);
      const routeData = window.lastRecommendationData || {};
      showCarExplanation(car, routeData);
    };

    // 클릭 시 상세 정보 + 햅틱 피드백
    el.addEventListener('click', openCarDetail);
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openCarDetail();
      }
    });
    train.appendChild(el);
  });

  container.appendChild(train);
}

// Chart.js 인스턴스 저장
let bpChartInstance = null;
let scoreChartInstance = null;

function renderBenefitPenaltyChart(carScores, containerId = 'bp-chart') {
  const container = document.getElementById(containerId);
  if (!container) return;

  const sorted = [...carScores].sort((a, b) => a.car - b.car);

  // 정규화: Benefit과 Penalty를 각각 0-100%로 표시
  const maxBenefit = Math.max(...sorted.map(c => c.benefit));
  const maxPenalty = Math.max(...sorted.map(c => c.penalty));

  const normBenefits = sorted.map(c => maxBenefit > 0 ? (c.benefit / maxBenefit) * 100 : 0);
  const normPenalties = sorted.map(c => maxPenalty > 0 ? (c.penalty / maxPenalty) * 100 : 0);

  container.innerHTML = `
    <h2 class="card-title">착석 기회 vs 혼잡 감점 분석</h2>
    <p class="card-desc">착석 기회와 혼잡 감점을 정규화하여 비교합니다. 100%는 각 항목의 최대값입니다.</p>
    <canvas id="bp-canvas" style="max-height: 400px;"></canvas>
  `;

  const canvas = document.getElementById('bp-canvas');
  const ctx = canvas.getContext('2d');

  if (bpChartInstance) {
    bpChartInstance.destroy();
  }

  // 테마 감지
  const isDark = !document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#7c829e' : '#5a6070';
  const gridColor = isDark ? '#2a3050' : '#d1d5dc';
  const tooltipBg = isDark ? 'rgba(21, 25, 41, 0.95)' : 'rgba(255, 255, 255, 0.95)';
  const tooltipText = isDark ? '#e8eaf0' : '#1a1d26';
  const tooltipBorder = isDark ? '#2a3050' : '#d1d5dc';

  bpChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: sorted.map(c => `${c.car}호차`),
      datasets: [
        {
          label: '착석 기회',
          data: normBenefits,
          backgroundColor: 'rgba(52, 211, 153, 0.8)',
          borderColor: 'rgba(52, 211, 153, 1)',
          borderWidth: 1,
          borderRadius: 4
        },
        {
          label: '혼잡 감점',
          data: normPenalties,
          backgroundColor: 'rgba(248, 113, 113, 0.8)',
          borderColor: 'rgba(248, 113, 113, 1)',
          borderWidth: 1,
          borderRadius: 4
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          labels: {
            color: textColor,
            font: { size: 12, family: "'Noto Sans KR', sans-serif" }
          }
        },
        tooltip: {
          backgroundColor: tooltipBg,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          borderColor: tooltipBorder,
          borderWidth: 1,
          padding: 12,
          displayColors: true,
          callbacks: {
            label: (context) => {
              const car = sorted[context.dataIndex];
              const datasetLabel = context.dataset.label;
              const normVal = context.parsed.y.toFixed(1);
              if (datasetLabel.includes('착석')) {
                return `착석 기회: ${normVal}% (원본: ${car.benefit.toFixed(1)})`;
              } else {
                return `혼잡 감점: ${normVal}% (원본: ${car.penalty.toFixed(1)})`;
              }
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor, drawBorder: false }
        },
        y: {
          ticks: {
            color: textColor,
            font: { size: 11 },
            callback: (value) => value + '%'
          },
          grid: { color: gridColor, drawBorder: false },
          max: 105,
          beginAtZero: true
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

  const isDark = !document.documentElement.getAttribute('data-theme') || document.documentElement.getAttribute('data-theme') === 'dark';
  const textColor = isDark ? '#7c829e' : '#5a6070';
  const gridColor = isDark ? '#2a3050' : '#d1d5dc';
  const tooltipBg = isDark ? 'rgba(21, 25, 41, 0.95)' : 'rgba(255, 255, 255, 0.95)';
  const tooltipText = isDark ? '#e8eaf0' : '#1a1d26';
  const tooltipBorder = isDark ? '#2a3050' : '#d1d5dc';

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
        borderWidth: 2,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: tooltipBg,
          titleColor: tooltipText,
          bodyColor: tooltipText,
          borderColor: tooltipBorder,
          borderWidth: 1,
          padding: 12,
          callbacks: {
            label: (context) => {
              const car = sorted[context.dataIndex];
              return [
                `점수: ${car.score.toFixed(1)}`,
                `순위: ${car.rank}위`,
                `착석 기회: ${car.benefit.toFixed(1)}`,
                `혼잡 감점: ${car.penalty.toFixed(1)}`
              ];
            }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor, drawBorder: false }
        },
        y: {
          ticks: { color: textColor, font: { size: 11 } },
          grid: { color: gridColor, drawBorder: false },
          beginAtZero: false
        }
      }
    }
  });
}
