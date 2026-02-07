// 피드백 시스템 모듈
class FeedbackSystem {
  constructor() {
    this.currentRecommendation = null;
    this.feedbackHistory = this.loadHistory();
  }

  // 피드백 기록 로드
  loadHistory() {
    try {
      const data = localStorage.getItem('metropy_feedback');
      return data ? JSON.parse(data) : [];
    } catch {
      return [];
    }
  }

  // 피드백 저장
  saveHistory() {
    try {
      localStorage.setItem('metropy_feedback', JSON.stringify(this.feedbackHistory));
    } catch (e) {
      console.error('피드백 저장 실패:', e);
    }
  }

  // 피드백 요청 표시
  showFeedbackRequest(recommendationData) {
    this.currentRecommendation = recommendationData;

    // 결과 섹션에 피드백 UI 추가
    const resultSection = document.getElementById('result-section');
    if (!resultSection) return;

    // 기존 피드백 UI 제거
    const existing = document.getElementById('feedback-widget');
    if (existing) existing.remove();

    const widget = document.createElement('div');
    widget.id = 'feedback-widget';
    widget.className = 'feedback-widget';
    widget.innerHTML = `
      <div class="feedback-card">
        <h3 class="feedback-title">🎯 추천이 도움이 되셨나요?</h3>
        <p class="feedback-subtitle">
          ${recommendationData.best_car}호차 추천에 대한 평가를 남겨주세요
        </p>
        <div class="feedback-options">
          <button class="feedback-btn helpful" onclick="feedbackSystem.submitFeedback('helpful')">
            <span class="feedback-icon">👍</span>
            <span>도움됨</span>
          </button>
          <button class="feedback-btn neutral" onclick="feedbackSystem.submitFeedback('neutral')">
            <span class="feedback-icon">😐</span>
            <span>보통</span>
          </button>
          <button class="feedback-btn not-helpful" onclick="feedbackSystem.submitFeedback('not-helpful')">
            <span class="feedback-icon">👎</span>
            <span>도움 안됨</span>
          </button>
        </div>
        <button class="feedback-skip" onclick="feedbackSystem.skipFeedback()">나중에</button>
      </div>
    `;

    // 결과 섹션 맨 아래에 추가
    resultSection.appendChild(widget);

    // 스크롤 애니메이션
    setTimeout(() => {
      widget.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 300);
  }

  // 피드백 제출
  submitFeedback(rating) {
    if (!this.currentRecommendation) return;

    const feedback = {
      timestamp: Date.now(),
      date: new Date().toISOString(),
      boarding: this.currentRecommendation.boarding,
      destination: this.currentRecommendation.destination,
      hour: this.currentRecommendation.hour,
      direction: this.currentRecommendation.direction,
      recommended_car: this.currentRecommendation.best_car,
      recommended_score: this.currentRecommendation.best_score,
      rating: rating,
      alpha: this.currentRecommendation.alpha,
      n_intermediate: this.currentRecommendation.n_intermediate
    };

    this.feedbackHistory.push(feedback);
    this.saveHistory();

    // 상세 피드백 요청 (선택사항)
    if (rating === 'not-helpful') {
      this.showDetailedFeedbackForm(feedback);
    } else {
      this.showThankYouMessage(rating);
    }

    // 통계 업데이트
    this.updateFeedbackStats(rating);
  }

  // 상세 피드백 폼 표시
  showDetailedFeedbackForm(feedback) {
    const widget = document.getElementById('feedback-widget');
    if (!widget) return;

    widget.innerHTML = `
      <div class="feedback-card">
        <h3 class="feedback-title">💭 무엇이 부족했나요?</h3>
        <p class="feedback-subtitle">선택사항이지만, 서비스 개선에 큰 도움이 됩니다</p>
        <div class="feedback-detailed-options">
          <label class="feedback-checkbox">
            <input type="checkbox" value="실제로 앉을 수 없었음">
            <span>추천 칸에서 실제로 앉을 수 없었어요</span>
          </label>
          <label class="feedback-checkbox">
            <input type="checkbox" value="다른 칸이 더 나았음">
            <span>다른 칸이 더 좋았어요</span>
          </label>
          <label class="feedback-checkbox">
            <input type="checkbox" value="혼잡도가 예상과 달랐음">
            <span>혼잡도가 예상과 달랐어요</span>
          </label>
          <label class="feedback-checkbox">
            <input type="checkbox" value="시간대가 맞지 않음">
            <span>시간대 예측이 맞지 않았어요</span>
          </label>
        </div>
        <textarea
          class="feedback-comment"
          placeholder="기타 의견을 자유롭게 작성해주세요 (선택사항)"
          maxlength="500"
        ></textarea>
        <div class="feedback-actions">
          <button class="btn-primary" onclick="feedbackSystem.submitDetailedFeedback(${feedback.timestamp})">
            제출
          </button>
          <button class="btn-secondary" onclick="feedbackSystem.skipDetailedFeedback()">
            건너뛰기
          </button>
        </div>
      </div>
    `;
  }

  // 상세 피드백 제출
  submitDetailedFeedback(timestamp) {
    const checkboxes = document.querySelectorAll('.feedback-checkbox input:checked');
    const comment = document.querySelector('.feedback-comment').value;

    const reasons = Array.from(checkboxes).map(cb => cb.value);

    // 기존 피드백에 상세 정보 추가
    const feedbackIndex = this.feedbackHistory.findIndex(f => f.timestamp === timestamp);
    if (feedbackIndex !== -1) {
      this.feedbackHistory[feedbackIndex].detailed_reasons = reasons;
      this.feedbackHistory[feedbackIndex].comment = comment;
      this.saveHistory();
    }

    this.showThankYouMessage('not-helpful');
  }

  // 상세 피드백 건너뛰기
  skipDetailedFeedback() {
    this.showThankYouMessage('not-helpful');
  }

  // 감사 메시지 표시
  showThankYouMessage(rating) {
    const widget = document.getElementById('feedback-widget');
    if (!widget) return;

    const messages = {
      'helpful': '감사합니다! 😊 계속해서 더 나은 추천을 제공하겠습니다.',
      'neutral': '의견 감사합니다. 서비스 개선에 반영하겠습니다.',
      'not-helpful': '소중한 피드백 감사합니다. 더 정확한 추천을 위해 노력하겠습니다.'
    };

    widget.innerHTML = `
      <div class="feedback-card feedback-success">
        <h3 class="feedback-title">✅ ${messages[rating]}</h3>
        <p class="feedback-subtitle">피드백이 저장되었습니다</p>
        <button class="btn-primary" onclick="feedbackSystem.closeFeedback()" style="margin-top: 12px">
          닫기
        </button>
      </div>
    `;

    // 3초 후 자동 닫기
    setTimeout(() => {
      this.closeFeedback();
    }, 3000);
  }

  // 피드백 건너뛰기
  skipFeedback() {
    this.closeFeedback();
  }

  // 피드백 위젯 닫기
  closeFeedback() {
    const widget = document.getElementById('feedback-widget');
    if (widget) {
      widget.classList.add('feedback-fadeout');
      setTimeout(() => widget.remove(), 300);
    }
    this.currentRecommendation = null;
  }

  // 피드백 통계 업데이트
  updateFeedbackStats(rating) {
    const stats = storage.getPreferences();
    if (!stats.feedbackStats) {
      stats.feedbackStats = {
        helpful: 0,
        neutral: 0,
        'not-helpful': 0,
        total: 0
      };
    }

    stats.feedbackStats[rating]++;
    stats.feedbackStats.total++;
    storage.updatePreferences(stats);
  }

  // 피드백 통계 가져오기
  getStats() {
    const stats = {
      helpful: 0,
      neutral: 0,
      'not-helpful': 0,
      total: 0,
      satisfaction_rate: 0
    };

    this.feedbackHistory.forEach(f => {
      stats[f.rating]++;
      stats.total++;
    });

    if (stats.total > 0) {
      stats.satisfaction_rate = ((stats.helpful / stats.total) * 100).toFixed(1);
    }

    return stats;
  }

  // 피드백 내보내기 (분석용)
  exportFeedback() {
    const data = {
      version: '1.0',
      exported_at: new Date().toISOString(),
      total_feedbacks: this.feedbackHistory.length,
      stats: this.getStats(),
      feedbacks: this.feedbackHistory
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `metropy-feedback-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // 피드백 통계 렌더링 (통계 페이지에서 사용)
  renderFeedbackStats(containerId = 'feedback-stats') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const stats = this.getStats();

    container.innerHTML = `
      <div class="feedback-stats-grid">
        <div class="stat-box">
          <div class="stat-number">${stats.total}</div>
          <div class="stat-label">총 피드백</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${stats.satisfaction_rate}%</div>
          <div class="stat-label">만족도</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${stats.helpful}</div>
          <div class="stat-label">도움됨</div>
        </div>
        <div class="stat-box">
          <div class="stat-number">${stats['not-helpful']}</div>
          <div class="stat-label">개선 필요</div>
        </div>
      </div>
      ${stats.total > 0 ? `
        <button class="btn-secondary" onclick="feedbackSystem.exportFeedback()" style="margin-top: 16px">
          피드백 데이터 내보내기
        </button>
      ` : ''}
    `;
  }
}

// 전역 인스턴스
const feedbackSystem = new FeedbackSystem();

// 추천 완료 시 피드백 요청
document.addEventListener('DOMContentLoaded', () => {
  // 기존 displayResult 함수에 훅 추가
  const originalDisplayResult = window.displayResult;
  if (originalDisplayResult) {
    window.displayResult = function(result) {
      originalDisplayResult(result);

      // 피드백 요청 (2초 지연)
      setTimeout(() => {
        if (storage.getPreferences().enableFeedback !== false) {
          feedbackSystem.showFeedbackRequest(result);
        }
      }, 2000);
    };
  }
});
