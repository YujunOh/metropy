// 통계 페이지 + PWA 서비스워커 등록 모듈
(function() {
  'use strict';

  // ==================== PWA 서비스워커 등록 ====================

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/service-worker.js')
        .then(reg => {
          console.log('SW registered:', reg);
          // 새 SW 업데이트 감지
          reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            if (newWorker) {
              newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'activated') {
                  showUpdateBanner();
                }
              });
            }
          });
        })
        .catch(err => console.log('SW registration failed:', err));
    });

    // SW 메시지 수신 (업데이트 알림)
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'SW_UPDATED') {
        showUpdateBanner();
      }
    });
  }

  function showUpdateBanner() {
    if (document.getElementById('sw-update-banner')) return; // 중복 방지
    const banner = document.createElement('div');
    banner.id = 'sw-update-banner';
    banner.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:var(--primary);color:#fff;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;z-index:10000;font-size:14px;box-shadow:0 -2px 10px rgba(0,0,0,0.2)';
    banner.innerHTML = '<span>앱이 업데이트되었습니다.</span><button onclick="location.reload()" style="background:#fff;color:var(--primary);border:none;padding:6px 16px;border-radius:6px;font-weight:600;cursor:pointer;font-size:13px">새로고침</button>';
    document.body.appendChild(banner);
  }

  // ==================== Chart.js 인스턴스 관리 ====================

  let carStatsChartInstance = null;
  let hourStatsChartInstance = null;

  // ==================== 통계 페이지 렌더링 ====================

  function renderStats() {
    const stats = storage.getStatistics();
    const content = document.getElementById('stats-content');

    if (!content) return;

    const daysSince = Math.floor((new Date() - new Date(stats.firstUsed)) / (1000 * 60 * 60 * 24));
    const avgPerDay = daysSince > 0 ? (stats.totalRecommendations / daysSince).toFixed(1) : 0;

    content.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:16px;margin:20px 0">
        <div class="stat-box">
          <div class="stat-number">${stats.totalRecommendations}</div>
          <div class="stat-label">총 이용 횟수</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${daysSince}</div>
          <div class="stat-label">이용 일수</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${avgPerDay}</div>
          <div class="stat-label">일평균 이용</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${Object.keys(stats.routeCount || {}).length}</div>
          <div class="stat-label">검색한 경로</div>
        </div>
      </div>
    `;

    // 칸별 통계 차트
    renderCarStatsChart(stats);

    // 시간대별 통계 (히스토리 기반)
    renderHourStatsChart();

    // 경로 랭킹
    renderRouteRanking(stats);
  }

  function renderCarStatsChart(stats) {
    const canvas = document.getElementById('car-stats-chart');
    if (!canvas) return;

    // 기존 차트 제거
    if (carStatsChartInstance) {
      carStatsChartInstance.destroy();
    }

    const carData = stats.carPreferences || {};
    if (Object.keys(carData).length === 0) {
      canvas.parentElement.innerHTML += '<p class="empty-state">아직 추천 데이터가 없습니다</p>';
      return;
    }

    // 1-10호차 전체 표시
    const labels = [];
    const data = [];
    for (let i = 1; i <= 10; i++) {
      labels.push(`${i}호차`);
      data.push(carData[i] || 0);
    }

    const ctx = canvas.getContext('2d');
    carStatsChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: '추천 횟수',
          data: data,
          backgroundColor: data.map((v, i) => {
            const max = Math.max(...data);
            return v === max ? 'rgba(52, 211, 153, 0.8)' : 'rgba(91, 140, 255, 0.7)';
          }),
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: 'var(--text-dim)' }, grid: { color: 'var(--border)' } },
          y: { ticks: { color: 'var(--text-dim)' }, grid: { color: 'var(--border)' }, beginAtZero: true }
        }
      }
    });
  }

  function renderHourStatsChart() {
    const canvas = document.getElementById('hour-stats-chart');
    if (!canvas) return;

    if (hourStatsChartInstance) {
      hourStatsChartInstance.destroy();
    }

    const history = storage.getHistory();
    if (history.length === 0) {
      canvas.parentElement.innerHTML += '<p class="empty-state">아직 검색 기록이 없습니다</p>';
      return;
    }

    // 시간대별 집계
    const hourCount = {};
    history.forEach(h => {
      const hour = h.hour || 8;
      hourCount[hour] = (hourCount[hour] || 0) + 1;
    });

    // 전체 시간대 표시 (5-25시, 24=00:00, 25=01:00)
    const labels = [];
    const data = [];
    for (let h = 5; h <= 25; h++) {
      const displayHour = h >= 24 ? h - 24 : h;
      labels.push(`${String(displayHour).padStart(2, '0')}시`);
      data.push(hourCount[h] || 0);
    }

    const ctx = canvas.getContext('2d');
    hourStatsChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '검색 횟수',
          data: data,
          borderColor: 'rgba(91, 140, 255, 1)',
          backgroundColor: 'rgba(91, 140, 255, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointHoverRadius: 6
        }]
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { ticks: { color: 'var(--text-dim)' }, grid: { color: 'var(--border)' } },
          y: { ticks: { color: 'var(--text-dim)' }, grid: { color: 'var(--border)' }, beginAtZero: true }
        }
      }
    });
  }

  function renderRouteRanking(stats) {
    const container = document.getElementById('route-ranking');
    if (!container) return;

    const routeCount = stats.routeCount || {};
    const routes = Object.entries(routeCount)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    if (routes.length === 0) {
      container.innerHTML = '<p class="empty-state">아직 검색 기록이 없습니다</p>';
      return;
    }

    const maxCount = routes[0][1];

    container.innerHTML = `
      <div class="route-ranking-list">
        ${routes.map(([route, count], i) => {
          const rankClass = i === 0 ? 'gold' : i === 1 ? 'silver' : i === 2 ? 'bronze' : '';
          const barWidth = (count / maxCount) * 100;
          return `
            <div class="route-ranking-item">
              <div class="route-rank ${rankClass}">${i + 1}</div>
              <div class="route-info">
                <div class="route-name">${route}</div>
                <div class="route-count">${count}회 검색</div>
              </div>
              <div class="route-bar-container">
                <div class="route-bar" style="width: ${barWidth}%"></div>
              </div>
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  // ==================== 데이터 내보내기/가져오기 ====================

  window.exportUserData = function() {
    const data = storage.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metropy-backup-${new Date().toISOString().split('T')[0]}.json`;
    a.click();
    URL.revokeObjectURL(url);
    showSuccess('데이터를 내보냈습니다.');
  };

  window.importUserData = function(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
      try {
        const data = JSON.parse(e.target.result);
        storage.importData(data);
        showSuccess('데이터를 가져왔습니다. 페이지를 새로고침합니다.');
        setTimeout(() => location.reload(), 1500);
      } catch (err) {
        showError('올바르지 않은 파일 형식입니다.');
      }
    };
    reader.readAsText(file);
  };

  window.confirmClearData = function() {
    if (confirm('모든 데이터(즐겨찾기, 히스토리, 통계)가 삭제됩니다. 계속하시겠습니까?')) {
      storage.clearAllData();
      showSuccess('모든 데이터가 초기화되었습니다.');
      setTimeout(() => location.reload(), 1500);
    }
  };

  // ==================== 페이지 전환 시 통계 업데이트 ====================

  window.renderStats = renderStats;

  const originalShowPage = window.showPage;
  window.showPage = function(pageName) {
    originalShowPage(pageName);
    if (pageName === 'stats') {
      setTimeout(() => {
        renderStats();
        if (window.feedbackSystem) {
          feedbackSystem.renderFeedbackStats('feedback-stats');
        }
      }, 100);
    }
  };

})();