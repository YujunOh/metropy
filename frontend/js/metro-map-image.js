// Metro Map Image - Interactive Line 2 map with zoom/pan and clickable stations
// Uses a PNG image overlay with station markers positioned by percentage coordinates
const MetroMapImage = (function() {
  'use strict';

  // ==================== Configuration ====================

  const IMG_SRC = '/static/img/naver_subway_line2.png';
  const MIN_ZOOM = 0.5;
  const MAX_ZOOM = 4.0;
  const ZOOM_STEP = 0.15;          // scroll sensitivity
  const PINCH_SENSITIVITY = 0.01;  // pinch-zoom sensitivity
  const MARKER_SIZE = 8;           // default marker radius in px
  const MARKER_HOVER_SIZE = 12;
  const MARKER_SELECTED_SIZE = 10;

  // Line 2 station positions as percentage of image dimensions (x%, y%)
  const STATION_POSITIONS = {
    "시청":               { x: 38.0, y: 26.0 },
    "을지로입구":         { x: 40.5, y: 26.0 },
    "을지로3가":          { x: 43.0, y: 26.0 },
    "을지로4가":          { x: 45.5, y: 26.5 },
    "동대문역사문화공원":  { x: 48.0, y: 26.5 },
    "신당":               { x: 50.5, y: 26.5 },
    "상왕십리":           { x: 53.0, y: 26.5 },
    "왕십리":             { x: 56.0, y: 27.0 },
    "한양대":             { x: 58.0, y: 29.5 },
    "뚝섬":               { x: 59.5, y: 32.0 },
    "성수":               { x: 60.5, y: 34.5 },
    "건대입구":           { x: 63.5, y: 37.0 },
    "구의":               { x: 67.0, y: 38.0 },
    "강변":               { x: 69.5, y: 38.0 },
    "잠실나루":           { x: 71.0, y: 42.0 },
    "잠실":               { x: 70.5, y: 46.0 },
    "잠실새내":           { x: 68.0, y: 50.5 },
    "종합운동장":         { x: 65.0, y: 53.5 },
    "삼성":               { x: 62.0, y: 56.5 },
    "선릉":               { x: 58.5, y: 59.0 },
    "역삼":               { x: 55.0, y: 61.5 },
    "강남":               { x: 52.0, y: 63.5 },
    "교대":               { x: 48.5, y: 65.0 },
    "서초":               { x: 46.0, y: 66.5 },
    "방배":               { x: 43.0, y: 68.5 },
    "사당":               { x: 40.0, y: 70.5 },
    "낙성대":             { x: 37.5, y: 68.5 },
    "서울대입구":         { x: 35.0, y: 66.5 },
    "봉천":               { x: 33.0, y: 64.0 },
    "신림":               { x: 31.0, y: 61.5 },
    "신대방":             { x: 29.0, y: 58.5 },
    "구로디지털단지":     { x: 27.5, y: 56.0 },
    "대림":               { x: 26.5, y: 53.0 },
    "신도림":             { x: 22.5, y: 49.0 },
    "문래":               { x: 25.0, y: 45.5 },
    "영등포구청":         { x: 26.5, y: 42.5 },
    "당산":               { x: 28.5, y: 39.0 },
    "합정":               { x: 31.5, y: 34.5 },
    "홍대입구":           { x: 33.0, y: 31.0 },
    "신촌":               { x: 34.0, y: 29.0 },
    "이대":               { x: 35.0, y: 27.5 },
    "아현":               { x: 36.0, y: 26.5 },
    "충정로":             { x: 37.0, y: 26.0 },
  };

  // ==================== Internal State ====================

  let container = null;     // outer container element
  let viewport = null;      // scrollable/pannable wrapper
  let imgWrapper = null;    // transformed element (holds image + markers)
  let imgEl = null;         // the <img> element
  let markerLayer = null;   // absolutely positioned div over the image
  let tooltip = null;       // station name tooltip element
  let markers = {};         // { stationName: markerElement }

  // Transform state
  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  // Drag state (mouse)
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragStartTX = 0;
  let dragStartTY = 0;

  // Touch state
  let lastTouchDist = 0;
  let lastTouchMidX = 0;
  let lastTouchMidY = 0;
  let isTouchDragging = false;

  // Route highlight state
  let highlightState = { boarding: null, destination: null, intermediates: [] };

  // ==================== Initialization ====================

  /**
   * Initialize the metro map inside the given container element.
   * @param {string} containerId - The id of the container div
   */
  function init(containerId) {
    container = document.getElementById(containerId);
    if (!container) {
      console.warn('[MetroMapImage] Container not found:', containerId);
      return;
    }

    // Inject styles once
    injectStyles();

    // Build the DOM structure
    buildDOM();

    // Create station markers
    createMarkers();

    // Attach event listeners
    attachEvents();

    console.log('[MetroMapImage] Initialized with', Object.keys(STATION_POSITIONS).length, 'stations');
  }

  // ==================== DOM Construction ====================

  function buildDOM() {
    container.classList.add('metro-map-container');

    // Viewport clips overflow during zoom/pan
    viewport = document.createElement('div');
    viewport.className = 'metro-map-viewport';

    // Wrapper holds the image and marker layer; receives CSS transform
    imgWrapper = document.createElement('div');
    imgWrapper.className = 'metro-map-wrapper';

    // The subway map image
    imgEl = document.createElement('img');
    imgEl.className = 'metro-map-img';
    imgEl.src = IMG_SRC;
    imgEl.alt = '서울 지하철 2호선 노선도';
    imgEl.draggable = false;
    imgEl.onerror = function() {
      console.error('[MetroMapImage] 노선도 이미지 로드 실패:', IMG_SRC);
      if (container) {
        container.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-muted)">' +
          '<p style="font-size:1.1rem;margin-bottom:8px">노선도 이미지를 불러올 수 없습니다</p>' +
          '<p style="font-size:0.85rem">새로고침하거나, 네트워크 연결을 확인해주세요.</p>' +
          '</div>';
      }
    };

    // Marker overlay layer (same size as image, positioned on top)
    markerLayer = document.createElement('div');
    markerLayer.className = 'metro-map-markers';

    // Tooltip element (hidden by default)
    tooltip = document.createElement('div');
    tooltip.className = 'metro-map-tooltip';
    tooltip.style.display = 'none';

    // Assemble
    imgWrapper.appendChild(imgEl);
    imgWrapper.appendChild(markerLayer);
    viewport.appendChild(imgWrapper);
    viewport.appendChild(tooltip);
    container.appendChild(viewport);

    // Add zoom controls
    const controls = document.createElement('div');
    controls.className = 'metro-map-controls';
    controls.innerHTML =
      '<button class="metro-map-btn" data-action="zoom-in" title="확대">+</button>' +
      '<button class="metro-map-btn" data-action="zoom-out" title="축소">&minus;</button>' +
      '<button class="metro-map-btn" data-action="reset" title="초기화">&#8634;</button>';
    container.appendChild(controls);

    controls.addEventListener('click', function(e) {
      const action = e.target.dataset.action;
      if (action === 'zoom-in') setZoom(scale + 0.3, null, null);
      else if (action === 'zoom-out') setZoom(scale - 0.3, null, null);
      else if (action === 'reset') resetView();
    });
  }

  // ==================== Station Markers ====================

  function createMarkers() {
    Object.keys(STATION_POSITIONS).forEach(function(name) {
      const pos = STATION_POSITIONS[name];
      const marker = document.createElement('div');
      marker.className = 'metro-map-marker';
      marker.dataset.station = name;
      marker.style.left = pos.x + '%';
      marker.style.top = pos.y + '%';

      markerLayer.appendChild(marker);
      markers[name] = marker;
    });
  }

  // ==================== Event Handling ====================

  function attachEvents() {
    // --- Mouse wheel zoom ---
    viewport.addEventListener('wheel', onWheel, { passive: false });

    // --- Mouse drag to pan ---
    viewport.addEventListener('mousedown', onMouseDown);
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);

    // --- Touch events (mobile) ---
    viewport.addEventListener('touchstart', onTouchStart, { passive: false });
    viewport.addEventListener('touchmove', onTouchMove, { passive: false });
    viewport.addEventListener('touchend', onTouchEnd);

    // --- Double-click to reset ---
    viewport.addEventListener('dblclick', function(e) {
      e.preventDefault();
      resetView();
    });

    // --- Station marker interactions ---
    markerLayer.addEventListener('click', onMarkerClick);
    markerLayer.addEventListener('mouseover', onMarkerHover);
    markerLayer.addEventListener('mouseout', onMarkerOut);
  }

  // ---------- Wheel Zoom ----------

  function onWheel(e) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -ZOOM_STEP : ZOOM_STEP;
    // Zoom toward cursor position
    const rect = viewport.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    setZoom(scale + delta, cx, cy);
  }

  // ---------- Mouse Pan ----------

  function onMouseDown(e) {
    // Only start drag on left button and not on a marker
    if (e.button !== 0) return;
    if (e.target.classList.contains('metro-map-marker')) return;
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    dragStartTX = translateX;
    dragStartTY = translateY;
    viewport.style.cursor = 'grabbing';
    e.preventDefault();
  }

  function onMouseMove(e) {
    if (!isDragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    translateX = dragStartTX + dx;
    translateY = dragStartTY + dy;
    applyTransform();
  }

  function onMouseUp() {
    if (isDragging) {
      isDragging = false;
      viewport.style.cursor = '';
    }
  }

  // ---------- Touch Pan & Pinch Zoom ----------

  function getTouchDistance(touches) {
    const dx = touches[0].clientX - touches[1].clientX;
    const dy = touches[0].clientY - touches[1].clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function getTouchMidpoint(touches) {
    return {
      x: (touches[0].clientX + touches[1].clientX) / 2,
      y: (touches[0].clientY + touches[1].clientY) / 2,
    };
  }

  function onTouchStart(e) {
    if (e.touches.length === 2) {
      // Pinch zoom start
      e.preventDefault();
      lastTouchDist = getTouchDistance(e.touches);
      var mid = getTouchMidpoint(e.touches);
      lastTouchMidX = mid.x;
      lastTouchMidY = mid.y;
    } else if (e.touches.length === 1) {
      // Single touch drag start
      if (e.target.classList.contains('metro-map-marker')) return;
      isTouchDragging = true;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      dragStartTX = translateX;
      dragStartTY = translateY;
    }
  }

  function onTouchMove(e) {
    if (e.touches.length === 2) {
      // Pinch zoom
      e.preventDefault();
      var dist = getTouchDistance(e.touches);
      var delta = (dist - lastTouchDist) * PINCH_SENSITIVITY;
      var mid = getTouchMidpoint(e.touches);
      var rect = viewport.getBoundingClientRect();
      var cx = mid.x - rect.left;
      var cy = mid.y - rect.top;
      setZoom(scale + delta, cx, cy);
      lastTouchDist = dist;
      lastTouchMidX = mid.x;
      lastTouchMidY = mid.y;
    } else if (e.touches.length === 1 && isTouchDragging) {
      // Single touch drag
      e.preventDefault();
      var dx = e.touches[0].clientX - dragStartX;
      var dy = e.touches[0].clientY - dragStartY;
      translateX = dragStartTX + dx;
      translateY = dragStartTY + dy;
      applyTransform();
    }
  }

  function onTouchEnd(e) {
    if (e.touches.length < 2) {
      lastTouchDist = 0;
    }
    if (e.touches.length === 0) {
      isTouchDragging = false;
    }
  }

  // ---------- Marker Click (Station Selection) ----------

  function onMarkerClick(e) {
    var target = e.target;
    if (!target.classList.contains('metro-map-marker')) return;

    var stationName = target.dataset.station;
    if (!stationName) return;

    // Stop the click from triggering a pan
    e.stopPropagation();

    selectStation(stationName);
    pulseMarker(target);
  }

  /**
   * Select a station on the map. Logic:
   *   - If no boarding station is set, set as boarding.
   *   - If boarding is set but not destination, set as destination.
   *   - If both are set, set as new boarding and clear destination.
   */
  function selectStation(stationName) {
    var boardingSel = document.getElementById('boarding');
    var destSel = document.getElementById('destination');
    var boardingSearch = document.getElementById('boarding-search');
    var destSearch = document.getElementById('destination-search');

    if (!boardingSel || !destSel) {
      console.warn('[MetroMapImage] Station select elements not found');
      return;
    }

    // Find station object from window.stations (populated by app.js)
    var stationsList = window.stations || [];
    var stationObj = stationsList.find(function(s) {
      return s.name === stationName;
    });
    var displayName = stationObj ? stationObj.name_display : stationName;

    var boardingVal = boardingSel.value;
    var destVal = destSel.value;

    if (!boardingVal) {
      // No boarding set -> set boarding
      setSelectValue(boardingSel, stationName);
      if (boardingSearch) boardingSearch.value = displayName;
    } else if (!destVal) {
      // Boarding set, no destination -> set destination
      // Unless the same station is clicked, then replace boarding
      if (boardingVal === stationName) return;
      setSelectValue(destSel, stationName);
      if (destSearch) destSearch.value = displayName;
    } else {
      // Both set -> cycle: set new boarding, clear destination
      setSelectValue(boardingSel, stationName);
      if (boardingSearch) boardingSearch.value = displayName;
      destSel.value = '';
      if (destSearch) destSearch.value = '';
    }

    // Update marker visual classes to reflect current selection
    updateSelectionMarkers();
  }

  /**
   * Set a <select> element's value, with fallback check.
   */
  function setSelectValue(selectEl, value) {
    for (var i = 0; i < selectEl.options.length; i++) {
      if (selectEl.options[i].value === value) {
        selectEl.value = value;
        return;
      }
    }
  }

  /**
   * Update marker CSS classes to show current boarding/destination selection.
   */
  function updateSelectionMarkers() {
    var boardingSel = document.getElementById('boarding');
    var destSel = document.getElementById('destination');
    var boardingVal = boardingSel ? boardingSel.value : '';
    var destVal = destSel ? destSel.value : '';

    Object.keys(markers).forEach(function(name) {
      var el = markers[name];
      el.classList.remove('marker-boarding', 'marker-destination', 'marker-intermediate');

      if (name === boardingVal) {
        el.classList.add('marker-boarding');
      } else if (name === destVal) {
        el.classList.add('marker-destination');
      }
    });
  }

  // ---------- Marker Hover (Tooltip) ----------

  function onMarkerHover(e) {
    var target = e.target;
    if (!target.classList.contains('metro-map-marker')) return;

    var stationName = target.dataset.station;
    if (!stationName) return;

    // Show tooltip near the marker
    tooltip.textContent = stationName;
    tooltip.style.display = 'block';

    // Position tooltip relative to viewport
    var rect = viewport.getBoundingClientRect();
    var markerRect = target.getBoundingClientRect();
    var tipX = markerRect.left - rect.left + markerRect.width / 2;
    var tipY = markerRect.top - rect.top - 8;

    tooltip.style.left = tipX + 'px';
    tooltip.style.top = tipY + 'px';
    tooltip.style.transform = 'translate(-50%, -100%)';

    target.classList.add('marker-hover');
  }

  function onMarkerOut(e) {
    var target = e.target;
    if (!target.classList.contains('metro-map-marker')) return;
    tooltip.style.display = 'none';
    target.classList.remove('marker-hover');
  }

  // ==================== Transform Helpers ====================

  /**
   * Set the zoom level, optionally centered on a point (cx, cy) in viewport coords.
   */
  function setZoom(newScale, cx, cy) {
    var oldScale = scale;
    scale = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, newScale));

    if (cx !== null && cy !== null && oldScale !== scale) {
      // Adjust translation so the point under the cursor stays fixed
      var ratio = scale / oldScale;
      translateX = cx - ratio * (cx - translateX);
      translateY = cy - ratio * (cy - translateY);
    }

    constrainPan();
    applyTransform();
  }

  /**
   * Apply the current transform state to the wrapper element.
   */
  function applyTransform() {
    imgWrapper.style.transform =
      'translate(' + translateX + 'px, ' + translateY + 'px) scale(' + scale + ')';
  }

  /**
   * Constrain panning so the image cannot be dragged entirely out of view.
   * Allows some overflow but keeps at least 20% of the image visible.
   */
  function constrainPan() {
    if (!viewport) return;
    var vw = viewport.clientWidth;
    var vh = viewport.clientHeight;
    var iw = imgWrapper.scrollWidth * scale;
    var ih = imgWrapper.scrollHeight * scale;

    var marginX = Math.max(vw * 0.2, 60);
    var marginY = Math.max(vh * 0.2, 60);

    var minX = vw - iw + marginX - (iw * (1 - 1 / scale)) / 2;
    var maxX = -marginX + (iw * (1 - 1 / scale)) / 2;
    var minY = vh - ih + marginY - (ih * (1 - 1 / scale)) / 2;
    var maxY = -marginY + (ih * (1 - 1 / scale)) / 2;

    // Only constrain if the image is larger than the viewport at current scale
    if (iw > vw) {
      translateX = Math.max(Math.min(translateX, maxX), minX);
    } else {
      // Center the image if it's smaller than the viewport
      translateX = (vw - imgWrapper.scrollWidth) / 2;
    }
    if (ih > vh) {
      translateY = Math.max(Math.min(translateY, maxY), minY);
    } else {
      translateY = (vh - imgWrapper.scrollHeight) / 2;
    }
  }

  // ==================== Visual Feedback ====================

  /**
   * Play a brief pulse animation on a marker element.
   */
  function pulseMarker(el) {
    el.classList.remove('marker-pulse');
    // Force reflow so re-adding the class triggers the animation
    void el.offsetWidth;
    el.classList.add('marker-pulse');
    setTimeout(function() {
      el.classList.remove('marker-pulse');
    }, 500);
  }

  // ==================== Public API ====================

  /**
   * Highlight a route on the map.
   * @param {string} boarding - Boarding station name
   * @param {string} destination - Destination station name
   * @param {string[]} intermediates - Array of intermediate station names
   */
  function highlightRoute(boarding, destination, intermediates) {
    highlightState = {
      boarding: boarding || null,
      destination: destination || null,
      intermediates: intermediates || [],
    };

    // Clear all highlight classes first
    Object.keys(markers).forEach(function(name) {
      var el = markers[name];
      el.classList.remove('marker-boarding', 'marker-destination', 'marker-intermediate');
    });

    // Apply highlight classes
    if (boarding && markers[boarding]) {
      markers[boarding].classList.add('marker-boarding');
    }
    if (destination && markers[destination]) {
      markers[destination].classList.add('marker-destination');
    }
    if (intermediates && intermediates.length > 0) {
      intermediates.forEach(function(name) {
        if (markers[name]) {
          markers[name].classList.add('marker-intermediate');
        }
      });
    }
  }

  /**
   * Reset zoom and pan to the default view.
   */
  function resetView() {
    scale = 1;
    translateX = 0;
    translateY = 0;
    applyTransform();
  }

  // ==================== CSS Injection ====================

  function injectStyles() {
    // Only inject once
    if (document.getElementById('metro-map-image-styles')) return;

    var css = [
      // --- Container ---
      '.metro-map-container {',
      '  position: relative;',
      '  width: 100%;',
      '  background: var(--surface, #151929);',
      '  border-radius: var(--radius, 16px);',
      '  overflow: hidden;',
      '  border: 1px solid var(--border, #2a3050);',
      '}',

      // --- Viewport ---
      '.metro-map-viewport {',
      '  position: relative;',
      '  width: 100%;',
      '  height: 500px;',
      '  overflow: hidden;',
      '  cursor: grab;',
      '  user-select: none;',
      '  -webkit-user-select: none;',
      '  touch-action: none;',
      '}',

      // --- Wrapper (receives transform) ---
      '.metro-map-wrapper {',
      '  position: relative;',
      '  width: 100%;',
      '  transform-origin: 0 0;',
      '  will-change: transform;',
      '  transition: none;',
      '}',

      // --- Image ---
      '.metro-map-img {',
      '  display: block;',
      '  width: 100%;',
      '  height: auto;',
      '  pointer-events: none;',
      '}',

      // --- Marker Layer ---
      '.metro-map-markers {',
      '  position: absolute;',
      '  top: 0;',
      '  left: 0;',
      '  width: 100%;',
      '  height: 100%;',
      '  pointer-events: none;',
      '}',

      // --- Station Marker (default) ---
      '.metro-map-marker {',
      '  position: absolute;',
      '  width: ' + MARKER_SIZE + 'px;',
      '  height: ' + MARKER_SIZE + 'px;',
      '  border-radius: 50%;',
      '  background: var(--green, #34d399);',
      '  border: 2px solid #fff;',
      '  transform: translate(-50%, -50%);',
      '  cursor: pointer;',
      '  pointer-events: auto;',
      '  transition: width 0.15s, height 0.15s, background 0.15s, box-shadow 0.15s;',
      '  z-index: 5;',
      '  box-shadow: 0 1px 4px rgba(0,0,0,0.3);',
      '}',

      // --- Hover state ---
      '.metro-map-marker.marker-hover {',
      '  width: ' + MARKER_HOVER_SIZE + 'px;',
      '  height: ' + MARKER_HOVER_SIZE + 'px;',
      '  z-index: 10;',
      '  box-shadow: 0 0 8px rgba(52,211,153,0.6);',
      '}',

      // --- Boarding (blue) ---
      '.metro-map-marker.marker-boarding {',
      '  width: ' + MARKER_SELECTED_SIZE + 'px;',
      '  height: ' + MARKER_SELECTED_SIZE + 'px;',
      '  background: var(--accent, #5b8cff);',
      '  border-color: #fff;',
      '  z-index: 8;',
      '  box-shadow: 0 0 10px rgba(91,140,255,0.7);',
      '}',

      // --- Destination (red) ---
      '.metro-map-marker.marker-destination {',
      '  width: ' + MARKER_SELECTED_SIZE + 'px;',
      '  height: ' + MARKER_SELECTED_SIZE + 'px;',
      '  background: var(--red, #f87171);',
      '  border-color: #fff;',
      '  z-index: 8;',
      '  box-shadow: 0 0 10px rgba(248,113,113,0.7);',
      '}',

      // --- Intermediate (bright green) ---
      '.metro-map-marker.marker-intermediate {',
      '  width: ' + MARKER_SELECTED_SIZE + 'px;',
      '  height: ' + MARKER_SELECTED_SIZE + 'px;',
      '  background: #10b981;',
      '  border-color: #fff;',
      '  z-index: 7;',
      '  box-shadow: 0 0 8px rgba(16,185,129,0.6);',
      '}',

      // --- Pulse animation ---
      '@keyframes metro-marker-pulse {',
      '  0% { transform: translate(-50%, -50%) scale(1); }',
      '  50% { transform: translate(-50%, -50%) scale(1.8); }',
      '  100% { transform: translate(-50%, -50%) scale(1); }',
      '}',
      '.metro-map-marker.marker-pulse {',
      '  animation: metro-marker-pulse 0.4s ease-out;',
      '}',

      // --- Tooltip ---
      '.metro-map-tooltip {',
      '  position: absolute;',
      '  background: var(--surface2, #1c2137);',
      '  color: var(--text, #e8eaf0);',
      '  font-size: 12px;',
      '  font-weight: 500;',
      '  padding: 4px 8px;',
      '  border-radius: 6px;',
      '  white-space: nowrap;',
      '  pointer-events: none;',
      '  z-index: 20;',
      '  box-shadow: 0 2px 8px rgba(0,0,0,0.4);',
      '  border: 1px solid var(--border, #2a3050);',
      '}',

      // --- Zoom Controls ---
      '.metro-map-controls {',
      '  position: absolute;',
      '  top: 12px;',
      '  right: 12px;',
      '  display: flex;',
      '  flex-direction: column;',
      '  gap: 6px;',
      '  z-index: 15;',
      '}',
      '.metro-map-btn {',
      '  width: 36px;',
      '  height: 36px;',
      '  border: 1px solid var(--border, #2a3050);',
      '  background: var(--surface, #151929);',
      '  color: var(--text, #e8eaf0);',
      '  font-size: 18px;',
      '  font-weight: 600;',
      '  border-radius: 8px;',
      '  cursor: pointer;',
      '  display: flex;',
      '  align-items: center;',
      '  justify-content: center;',
      '  transition: background 0.15s, border-color 0.15s;',
      '  line-height: 1;',
      '}',
      '.metro-map-btn:hover {',
      '  background: var(--surface2, #1c2137);',
      '  border-color: var(--accent, #5b8cff);',
      '}',

      // --- Responsive ---
      '@media (max-width: 768px) {',
      '  .metro-map-viewport {',
      '    height: 350px;',
      '  }',
      '}',
    ].join('\n');

    var styleEl = document.createElement('style');
    styleEl.id = 'metro-map-image-styles';
    styleEl.textContent = css;
    document.head.appendChild(styleEl);
  }

  // ==================== Module Exports ====================

  return {
    init: init,
    highlightRoute: highlightRoute,
    resetView: resetView,
    // Expose station positions for external use (read-only intent)
    STATION_POSITIONS: STATION_POSITIONS,
  };

})();
