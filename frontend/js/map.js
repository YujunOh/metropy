// Kakao Map 연동 모듈 - 2호선 노선 시각화
const MetroMap = (function() {
  let map = null;
  let polyline = null;
  let markers = [];
  let infoWindows = [];
  let isInitialized = false;

  // 2호선 전체 역 좌표 (순환선 순서)
  const LINE2_STATIONS = {
    '시청': { lat: 37.5662, lng: 126.9779, order: 0 },
    '을지로입구': { lat: 37.5658, lng: 126.9822, order: 1 },
    '을지로3가': { lat: 37.5662, lng: 126.9914, order: 2 },
    '을지로4가': { lat: 37.5669, lng: 127.0017, order: 3 },
    '동대문역사문화공원': { lat: 37.5652, lng: 127.0079, order: 4 },
    '신당': { lat: 37.5661, lng: 127.0177, order: 5 },
    '상왕십리': { lat: 37.5658, lng: 127.0294, order: 6 },
    '왕십리': { lat: 37.5617, lng: 127.0377, order: 7 },
    '한양대': { lat: 37.5559, lng: 127.0442, order: 8 },
    '뚝섬': { lat: 37.5467, lng: 127.0472, order: 9 },
    '성수': { lat: 37.5445, lng: 127.0557, order: 10 },
    '건대입구': { lat: 37.5401, lng: 127.0695, order: 11 },
    '구의': { lat: 37.5371, lng: 127.0855, order: 12 },
    '강변': { lat: 37.5348, lng: 127.0944, order: 13 },
    '잠실나루': { lat: 37.5202, lng: 127.1020, order: 14 },
    '잠실': { lat: 37.5133, lng: 127.1000, order: 15 },
    '잠실새내': { lat: 37.5112, lng: 127.0860, order: 16 },
    '종합운동장': { lat: 37.5107, lng: 127.0735, order: 17 },
    '삼성': { lat: 37.5088, lng: 127.0633, order: 18 },
    '선릉': { lat: 37.5045, lng: 127.0493, order: 19 },
    '역삼': { lat: 37.5004, lng: 127.0364, order: 20 },
    '강남': { lat: 37.4979, lng: 127.0276, order: 21 },
    '교대': { lat: 37.4934, lng: 127.0145, order: 22 },
    '서초': { lat: 37.4916, lng: 127.0078, order: 23 },
    '방배': { lat: 37.4814, lng: 126.9976, order: 24 },
    '사당': { lat: 37.4766, lng: 126.9816, order: 25 },
    '낙성대': { lat: 37.4768, lng: 126.9636, order: 26 },
    '서울대입구': { lat: 37.4814, lng: 126.9527, order: 27 },
    '봉천': { lat: 37.4821, lng: 126.9426, order: 28 },
    '신림': { lat: 37.4842, lng: 126.9296, order: 29 },
    '신대방': { lat: 37.4872, lng: 126.9130, order: 30 },
    '구로디지털단지': { lat: 37.4851, lng: 126.9015, order: 31 },
    '대림': { lat: 37.4932, lng: 126.8956, order: 32 },
    '신도림': { lat: 37.5089, lng: 126.8913, order: 33 },
    '문래': { lat: 37.5178, lng: 126.8950, order: 34 },
    '영등포구청': { lat: 37.5244, lng: 126.8960, order: 35 },
    '당산': { lat: 37.5345, lng: 126.9025, order: 36 },
    '합정': { lat: 37.5494, lng: 126.9139, order: 37 },
    '홍대입구': { lat: 37.5571, lng: 126.9245, order: 38 },
    '신촌': { lat: 37.5559, lng: 126.9368, order: 39 },
    '이대': { lat: 37.5566, lng: 126.9458, order: 40 },
    '아현': { lat: 37.5573, lng: 126.9567, order: 41 },
    '충정로': { lat: 37.5598, lng: 126.9637, order: 42 }
  };

  // 2호선 색상
  const LINE2_COLOR = '#3CB44A';

  // 지도 초기화
  function init(containerId) {
    if (typeof kakao === 'undefined' || !kakao.maps) {
      console.error('Kakao Maps SDK가 로드되지 않았습니다.');
      return false;
    }

    const container = document.getElementById(containerId);
    if (!container) {
      console.error(`Map container '${containerId}' not found`);
      return false;
    }

    // 서울 중심 좌표
    const center = new kakao.maps.LatLng(37.5326, 127.0246);

    map = new kakao.maps.Map(container, {
      center: center,
      level: 8 // 줌 레벨 (작을수록 확대)
    });

    // 지도 컨트롤 추가
    const zoomControl = new kakao.maps.ZoomControl();
    map.addControl(zoomControl, kakao.maps.ControlPosition.RIGHT);

    isInitialized = true;

    // 전체 노선 그리기
    drawFullLine();

    return true;
  }

  // 전체 2호선 노선 그리기
  function drawFullLine() {
    if (!map) return;

    // 순서대로 정렬
    const orderedStations = Object.entries(LINE2_STATIONS)
      .sort((a, b) => a[1].order - b[1].order);

    const path = orderedStations.map(([name, data]) =>
      new kakao.maps.LatLng(data.lat, data.lng)
    );

    // 순환선이므로 시작점으로 돌아오기
    path.push(path[0]);

    // 기존 폴리라인 제거
    if (polyline) {
      polyline.setMap(null);
    }

    polyline = new kakao.maps.Polyline({
      path: path,
      strokeWeight: 5,
      strokeColor: LINE2_COLOR,
      strokeOpacity: 0.7,
      strokeStyle: 'solid'
    });

    polyline.setMap(map);
  }

  // 경로 하이라이트 (출발-도착)
  function highlightRoute(boarding, destination, intermediates) {
    if (!map) return;

    // 기존 마커 제거
    clearMarkers();

    const boardingData = LINE2_STATIONS[boarding];
    const destData = LINE2_STATIONS[destination];

    if (!boardingData || !destData) {
      console.warn('역 좌표를 찾을 수 없습니다:', boarding, destination);
      return;
    }

    // 출발역 마커
    addMarker(boardingData.lat, boardingData.lng, boarding, 'start');

    // 도착역 마커
    addMarker(destData.lat, destData.lng, destination, 'end');

    // 중간역 마커들
    if (intermediates && intermediates.length > 0) {
      intermediates.forEach(stationName => {
        const data = LINE2_STATIONS[stationName];
        if (data) {
          addMarker(data.lat, data.lng, stationName, 'intermediate');
        }
      });
    }

    // 경로 라인 하이라이트
    highlightPath(boarding, destination, intermediates);

    // 지도 범위 조정
    fitBounds(boarding, destination, intermediates);
  }

  // 경로 라인 하이라이트
  function highlightPath(boarding, destination, intermediates) {
    // 이전 하이라이트 라인이 있으면 제거
    if (window.highlightPolyline) {
      window.highlightPolyline.setMap(null);
    }

    const allStations = [boarding, ...(intermediates || []), destination];
    const path = allStations
      .map(name => {
        const data = LINE2_STATIONS[name];
        return data ? new kakao.maps.LatLng(data.lat, data.lng) : null;
      })
      .filter(p => p !== null);

    if (path.length < 2) return;

    window.highlightPolyline = new kakao.maps.Polyline({
      path: path,
      strokeWeight: 8,
      strokeColor: '#5B8CFF',
      strokeOpacity: 0.9,
      strokeStyle: 'solid'
    });

    window.highlightPolyline.setMap(map);
  }

  // 마커 추가
  function addMarker(lat, lng, title, type) {
    const position = new kakao.maps.LatLng(lat, lng);

    // 마커 이미지 설정
    let markerImage;
    const imageSize = new kakao.maps.Size(32, 32);
    const imageOption = { offset: new kakao.maps.Point(16, 32) };

    if (type === 'start') {
      // 출발역: 초록색
      markerImage = new kakao.maps.MarkerImage(
        'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/markerStar.png',
        imageSize, imageOption
      );
    } else if (type === 'end') {
      // 도착역: 빨간색
      markerImage = new kakao.maps.MarkerImage(
        'https://t1.daumcdn.net/localimg/localimages/07/mapapidoc/marker_red.png',
        imageSize, imageOption
      );
    }

    const marker = new kakao.maps.Marker({
      position: position,
      title: title,
      image: markerImage || undefined
    });

    marker.setMap(map);
    markers.push(marker);

    // 인포윈도우
    const infoContent = `
      <div style="padding:8px 12px;font-size:13px;font-weight:600;white-space:nowrap;">
        ${type === 'start' ? '🚇 출발: ' : type === 'end' ? '🏁 도착: ' : '➡️ '}${title}
      </div>
    `;

    const infoWindow = new kakao.maps.InfoWindow({
      content: infoContent
    });

    // 출발/도착역은 기본으로 표시
    if (type === 'start' || type === 'end') {
      infoWindow.open(map, marker);
      infoWindows.push(infoWindow);
    }

    // 마커 클릭 시 인포윈도우 토글
    kakao.maps.event.addListener(marker, 'click', function() {
      if (infoWindow.getMap()) {
        infoWindow.close();
      } else {
        infoWindow.open(map, marker);
      }
    });
  }

  // 마커 모두 제거
  function clearMarkers() {
    markers.forEach(m => m.setMap(null));
    markers = [];
    infoWindows.forEach(iw => iw.close());
    infoWindows = [];

    if (window.highlightPolyline) {
      window.highlightPolyline.setMap(null);
      window.highlightPolyline = null;
    }
  }

  // 지도 범위 조정
  function fitBounds(boarding, destination, intermediates) {
    const bounds = new kakao.maps.LatLngBounds();

    const allStations = [boarding, destination, ...(intermediates || [])];
    allStations.forEach(name => {
      const data = LINE2_STATIONS[name];
      if (data) {
        bounds.extend(new kakao.maps.LatLng(data.lat, data.lng));
      }
    });

    map.setBounds(bounds, 50); // 50px 패딩
  }

  // 전체 노선 보기
  function showFullLine() {
    if (!map) return;

    clearMarkers();

    // 서울 중심으로 리셋
    map.setCenter(new kakao.maps.LatLng(37.5326, 127.0246));
    map.setLevel(8);
  }

  // 특정 역으로 이동
  function panToStation(stationName) {
    const data = LINE2_STATIONS[stationName];
    if (data && map) {
      map.panTo(new kakao.maps.LatLng(data.lat, data.lng));
      map.setLevel(5);
    }
  }

  // 지도 표시/숨기기
  function toggle(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (container.classList.contains('map-visible')) {
      container.classList.remove('map-visible');
      container.style.height = '0';
    } else {
      container.classList.add('map-visible');
      container.style.height = '400px';

      // 지도가 초기화되지 않았으면 초기화
      if (!isInitialized) {
        setTimeout(() => init(containerId), 100);
      } else {
        // 이미 초기화됨 - 리사이즈 트리거
        setTimeout(() => {
          if (map) map.relayout();
        }, 100);
      }
    }
  }

  // 역 좌표 데이터 가져오기
  function getStationCoords(stationName) {
    return LINE2_STATIONS[stationName] || null;
  }

  // 모든 역 목록
  function getAllStations() {
    return Object.keys(LINE2_STATIONS);
  }

  return {
    init,
    highlightRoute,
    showFullLine,
    panToStation,
    toggle,
    clearMarkers,
    getStationCoords,
    getAllStations,
    get isReady() { return isInitialized; }
  };
})();

// 전역 접근용
window.MetroMap = MetroMap;
