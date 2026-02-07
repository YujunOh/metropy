// 즐겨찾기 & 히스토리 UI 관리
function initQuickAccess() {
  updateQuickAccess();

  // 추천 완료 시 히스토리에 추가
  const originalDoRecommend = window.doRecommend;
  window.doRecommend = async function() {
    await originalDoRecommend();
    const boarding = document.getElementById('boarding').value;
    const destination = document.getElementById('destination').value;
    const hour = parseInt(document.getElementById('hour-slider').value);

    if (boarding && destination && storage.getPreferences().autoSaveHistory) {
      storage.addHistory({ boarding, destination, hour });
      updateQuickAccess();
    }
  };
}

function updateQuickAccess() {
  const favorites = storage.getFavorites();
  const history = storage.getHistory();
  const container = document.getElementById('quick-access');
  const favList = document.getElementById('favorites-list');
  const histList = document.getElementById('history-list');

  // 표시 여부
  if (favorites.length === 0 && history.length === 0) {
    container.style.display = 'none';
    return;
  }
  container.style.display = 'grid';

  // 즐겨찾기 렌더링
  if (favorites.length > 0) {
    favList.innerHTML = favorites.map(fav => `
      <div class="quick-item" onclick="loadRoute('${fav.boarding}', '${fav.destination}', ${fav.hour})">
        <div class="quick-item-info">
          <span class="quick-item-name">${fav.name}</span>
          <span class="quick-item-route">${fav.boarding} → ${fav.destination}</span>
        </div>
        <div class="quick-item-actions">
          <button class="icon-btn" onclick="event.stopPropagation(); removeFavorite(${fav.id})" title="삭제">🗑️</button>
        </div>
      </div>
    `).join('');
  } else {
    favList.innerHTML = '<p class="empty-state">즐겨찾기가 없습니다</p>';
  }

  // 히스토리 렌더링
  if (history.length > 0) {
    histList.innerHTML = history.slice(0, 5).map(h => `
      <div class="quick-item" onclick="loadRoute('${h.boarding}', '${h.destination}', ${h.hour})">
        <div class="quick-item-info">
          <span class="quick-item-route">${h.boarding} → ${h.destination}</span>
        </div>
      </div>
    `).join('');
  } else {
    histList.innerHTML = '<p class="empty-state">검색 기록이 없습니다</p>';
  }

  // 즐겨찾기 버튼 업데이트
  updateFavoriteButton();
}

function loadRoute(boarding, destination, hour = 8) {
  document.getElementById('boarding').value = boarding;
  document.getElementById('destination').value = destination;
  document.getElementById('hour-slider').value = hour;
  updateHourLabel();
  updateFavoriteButton();
}

function updateFavoriteButton() {
  const boarding = document.getElementById('boarding').value;
  const destination = document.getElementById('destination').value;
  const btn = document.getElementById('add-favorite-btn');

  if (!boarding || !destination) {
    btn.style.display = 'none';
    return;
  }

  btn.style.display = 'block';
  const isFav = storage.isFavorite(boarding, destination);
  btn.textContent = isFav ? '⭐' : '☆';
  btn.onclick = () => toggleFavorite(boarding, destination);
}

function showFavoriteNameModal(defaultName) {
  return new Promise((resolve) => {
    const overlay = document.createElement('div');
    const safeName = String(defaultName || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');

    overlay.className = 'modal-overlay active';
    overlay.innerHTML = `
      <div class="modal" style="max-width:360px">
        <h3 style="margin:0 0 12px">즐겨찾기 이름</h3>
        <input type="text" id="fav-name-input" value="${safeName}"
               style="width:100%;padding:10px;border:1px solid var(--border);border-radius:8px;background:var(--surface2);color:var(--text);font-size:15px;box-sizing:border-box"
               maxlength="30" autofocus>
        <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
          <button class="btn" id="fav-name-cancel"
                  style="background:var(--surface2);color:var(--text-muted)">취소</button>
          <button class="btn btn-primary" id="fav-name-confirm">저장</button>
        </div>
      </div>`;

    document.body.appendChild(overlay);
    const input = overlay.querySelector('#fav-name-input');
    const confirm = overlay.querySelector('#fav-name-confirm');
    const cancel = overlay.querySelector('#fav-name-cancel');

    const close = (value) => {
      overlay.remove();
      resolve(value);
    };

    input.select();
    confirm.addEventListener('click', () => {
      const value = input.value.trim();
      close(value || null);
    });
    cancel.addEventListener('click', () => close(null));
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') confirm.click();
      if (e.key === 'Escape') close(null);
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) close(null);
    });
  });
}

async function toggleFavorite(boarding, destination) {
  const isFav = storage.isFavorite(boarding, destination);
  const hour = parseInt(document.getElementById('hour-slider').value);

  if (isFav) {
    const favorites = storage.getFavorites();
    const fav = favorites.find(f => f.boarding === boarding && f.destination === destination);
    if (fav) {
      storage.removeFavorite(fav.id);
      showSuccess('즐겨찾기에서 제거했습니다');
    }
  } else {
    const name = await showFavoriteNameModal(`${boarding} → ${destination}`);
    if (name) {
      storage.addFavorite({ boarding, destination, hour, name });
      showSuccess('즐겨찾기에 추가했습니다');
    }
  }

  updateQuickAccess();
  updateFavoriteButton();
}

function removeFavorite(id) {
  if (confirm('즐겨찾기에서 삭제하시겠습니까?')) {
    storage.removeFavorite(id);
    updateQuickAccess();
    showSuccess('삭제했습니다');
  }
}

// 역 선택 시 즐겨찾기 버튼 업데이트
document.addEventListener('DOMContentLoaded', () => {
  const boarding = document.getElementById('boarding');
  const destination = document.getElementById('destination');

  if (boarding && destination) {
    boarding.addEventListener('change', updateFavoriteButton);
    destination.addEventListener('change', updateFavoriteButton);
  }

  initQuickAccess();
});
