// 경로 비교 모듈
(function() {
  let compareMode = false;

  // 비교 모드 토글
  window.toggleCompareMode = function() {
    const section = document.getElementById('compare-section');
    const btn = document.getElementById('compare-toggle-btn');

    if (!section || !btn) return;

    compareMode = !compareMode;

    if (compareMode) {
      section.style.display = 'block';
      btn.textContent = '비교 닫기';
      btn.classList.add('active');
      initCompareSelects();
    } else {
      section.style.display = 'none';
      btn.textContent = '+ 다른 경로와 비교';
      btn.classList.remove('active');
    }
  };

  // 비교용 역 선택 초기화
  function initCompareSelects() {
    const stations = window.stations || [];
    const boarding = document.getElementById('compare-boarding');
    const destination = document.getElementById('compare-destination');

    if (!boarding || !destination || !stations.length) return;

    [boarding, destination].forEach(sel => {
      sel.innerHTML = '<option value="">역 선택...</option>';
      stations.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s.name;
        opt.textContent = s.name_display;
        sel.appendChild(opt);
      });
    });

    // 자동완성 초기화
    if (typeof AutocompleteUI !== 'undefined') {
      new AutocompleteUI('compare-boarding-search', 'compare-boarding', stations);
      new AutocompleteUI('compare-destination-search', 'compare-destination', stations);
    }
  }

  // 비교 실행
  window.runComparison = async function() {
    const currentResult = window.lastRecommendationData;
    if (!currentResult) {
      showError('먼저 기본 경로를 검색해주세요.');
      return;
    }

    const compareBoarding = document.getElementById('compare-boarding').value;
    const compareDestination = document.getElementById('compare-destination').value;

    if (!compareBoarding || !compareDestination) {
      showError('비교할 출발역과 도착역을 선택해주세요.');
      return;
    }

    if (compareBoarding === compareDestination) {
      showError('출발역과 도착역이 같습니다.');
      return;
    }

    const hour = parseInt(document.getElementById('hour-slider').value);

    try {
      showLoading();
      const compareResult = await API.recommend(compareBoarding, compareDestination, hour);
      displayComparison(currentResult, compareResult);
    } catch (e) {
      showError('비교 경로 분석 실패: ' + e.message);
    } finally {
      hideLoading();
    }
  };

  // 비교 결과 표시
  function displayComparison(route1, route2) {
    const container = document.getElementById('comparison-result');
    if (!container) return;

    // 어느 경로가 더 좋은지 판단
    const score1 = route1.best_score;
    const score2 = route2.best_score;
    const spread1 = route1.score_spread;
    const spread2 = route2.score_spread;

    // 복합 점수: 최고 점수 + 점수 분산 (분산이 클수록 칸 선택이 중요)
    const composite1 = score1 + spread1 * 0.5;
    const composite2 = score2 + spread2 * 0.5;

    const winner = composite1 >= composite2 ? 'current' : 'compare';

    container.innerHTML = `
      <div class="comparison-results-grid">
        <!-- 현재 경로 -->
        <div class="comparison-route-card ${winner === 'current' ? 'winner' : ''}">
          <div class="comparison-route-header">
            <span class="comparison-route-name">${route1.boarding} → ${route1.destination}</span>
            <span class="comparison-route-badge ${winner === 'current' ? 'best' : 'current'}">
              ${winner === 'current' ? '추천' : '현재'}
            </span>
          </div>
          <div class="comparison-stats">
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route1.best_car}호차</div>
              <div class="comparison-stat-label">추천 칸</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route1.best_score.toFixed(1)}</div>
              <div class="comparison-stat-label">최고 점수</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route1.score_spread.toFixed(1)}</div>
              <div class="comparison-stat-label">점수 차이</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route1.n_intermediate}</div>
              <div class="comparison-stat-label">경유 역</div>
            </div>
          </div>
        </div>

        <!-- 비교 경로 -->
        <div class="comparison-route-card ${winner === 'compare' ? 'winner' : ''}">
          <div class="comparison-route-header">
            <span class="comparison-route-name">${route2.boarding} → ${route2.destination}</span>
            <span class="comparison-route-badge ${winner === 'compare' ? 'best' : 'compare'}">
              ${winner === 'compare' ? '추천' : '비교'}
            </span>
          </div>
          <div class="comparison-stats">
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route2.best_car}호차</div>
              <div class="comparison-stat-label">추천 칸</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route2.best_score.toFixed(1)}</div>
              <div class="comparison-stat-label">최고 점수</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route2.score_spread.toFixed(1)}</div>
              <div class="comparison-stat-label">점수 차이</div>
            </div>
            <div class="comparison-stat">
              <div class="comparison-stat-value">${route2.n_intermediate}</div>
              <div class="comparison-stat-label">경유 역</div>
            </div>
          </div>
        </div>
      </div>

      <div class="comparison-verdict">
        <p class="comparison-verdict-text">
          ${generateVerdict(route1, route2, winner)}
        </p>
      </div>
    `;
  }

  // 비교 결론 생성
  function generateVerdict(route1, route2, winner) {
    const winnerRoute = winner === 'current' ? route1 : route2;
    const loserRoute = winner === 'current' ? route2 : route1;

    const scoreDiff = Math.abs(winnerRoute.best_score - loserRoute.best_score).toFixed(1);
    const spreadDiff = (winnerRoute.score_spread - loserRoute.score_spread).toFixed(1);

    let verdict = `<strong>${winnerRoute.boarding} → ${winnerRoute.destination}</strong> 경로가 `;

    if (parseFloat(scoreDiff) > 3) {
      verdict += `${scoreDiff}점 더 높은 착석 점수를 보입니다. `;
    } else {
      verdict += `비슷한 착석 점수를 보이지만 `;
    }

    if (parseFloat(spreadDiff) > 2) {
      verdict += `칸 선택에 따른 점수 차이가 ${Math.abs(spreadDiff)}점 더 크므로 올바른 칸 선택이 더 중요합니다.`;
    } else if (parseFloat(spreadDiff) < -2) {
      verdict += `칸 선택에 따른 영향이 적어 어느 칸을 타더라도 비슷합니다.`;
    } else {
      verdict += `두 경로 모두 칸 선택이 유사하게 중요합니다.`;
    }

    return verdict;
  }
})();
