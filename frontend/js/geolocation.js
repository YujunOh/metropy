// GPS 기반 역 자동 감지 모듈
class GeoLocationService {
  constructor() {
    this.enabled = false;
    this.currentPosition = null;
    this.watchId = null;
  }

  // GPS 기능 사용 가능 여부 확인
  isAvailable() {
    return 'geolocation' in navigator;
  }

  // 두 좌표 사이의 거리 계산 (Haversine formula, km)
  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // 지구 반지름 (km)
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);
    const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  toRad(degrees) {
    return degrees * (Math.PI / 180);
  }

  // 가장 가까운 역 찾기
  findNearestStation(latitude, longitude, stations) {
    if (!stations || stations.length === 0) {
      return null;
    }

    let nearest = null;
    let minDistance = Infinity;

    stations.forEach(station => {
      // 역 좌표 데이터가 있다고 가정 (실제로는 API에서 가져와야 함)
      if (station.latitude && station.longitude) {
        const distance = this.calculateDistance(
          latitude,
          longitude,
          station.latitude,
          station.longitude
        );

        if (distance < minDistance) {
          minDistance = distance;
          nearest = station;
        }
      }
    });

    // 5km 이상이면 2호선 근처가 아닌 것으로 판단
    if (minDistance > 5.0) {
      return {
        station: nearest,
        distance: minDistance,
        tooFar: true
      };
    }

    return {
      station: nearest,
      distance: minDistance,
      tooFar: false
    };
  }

  // 현재 위치 가져오기
  async getCurrentPosition() {
    return new Promise((resolve, reject) => {
      if (!this.isAvailable()) {
        reject(new Error('GPS를 지원하지 않는 브라우저입니다'));
        return;
      }

      navigator.geolocation.getCurrentPosition(
        (position) => {
          this.currentPosition = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy: position.coords.accuracy,
            timestamp: position.timestamp
          };
          resolve(this.currentPosition);
        },
        (error) => {
          let errorMessage = 'GPS 위치를 가져올 수 없습니다';
          switch (error.code) {
            case error.PERMISSION_DENIED:
              errorMessage = 'GPS 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해주세요.';
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage = 'GPS 위치 정보를 사용할 수 없습니다.';
              break;
            case error.TIMEOUT:
              errorMessage = 'GPS 위치 요청 시간이 초과되었습니다.';
              break;
          }
          reject(new Error(errorMessage));
        },
        {
          enableHighAccuracy: true,
          timeout: 10000,
          maximumAge: 60000
        }
      );
    });
  }

  // 역 자동 선택
  async autoSelectNearestStation(stationSelectId = 'boarding') {
    try {
      if (typeof showLoading === 'function') showLoading();

      // 현재 위치 가져오기
      const position = await this.getCurrentPosition();

      // 역 목록 가져오기
      const stationList = window.stations || [];

      if (stationList.length === 0) {
        throw new Error('역 목록을 불러오는 중입니다. 잠시 후 다시 시도해주세요.');
      }

      // 좌표 매칭으로 가장 가까운 역 찾기
      const result = await this.fetchNearestStationFromAPI(
        position.latitude,
        position.longitude
      );

      if (result && result.station) {
        // 5km 이상이면 2호선 근처가 아닌 것으로 판단
        if (result.tooFar) {
          const distStr = result.distance < 1
            ? (result.distance * 1000).toFixed(0) + 'm'
            : result.distance.toFixed(1) + 'km';
          throw new Error(`2호선 역 근처가 아닙니다 (가장 가까운 역까지 ${distStr}). 직접 출발역을 선택해주세요.`);
        }

        const select = document.getElementById(stationSelectId);
        const input = document.getElementById(`${stationSelectId}-search`);

        if (select && result.station.name) {
          select.value = result.station.name;
          if (input) {
            input.value = result.station.name_display || result.station.name;
          }

          const event = new Event('change', { bubbles: true });
          select.dispatchEvent(event);

          if (typeof showSuccess === 'function') {
            showSuccess(
              `📍 가장 가까운 역: ${result.station.name_display || result.station.name} (${result.distance < 1 ? (result.distance * 1000).toFixed(0) + 'm' : result.distance.toFixed(1) + 'km'})`
            );
          }
        }
      } else {
        throw new Error('근처에 2호선 역을 찾을 수 없습니다');
      }
    } catch (error) {
      if (typeof showError === 'function') {
        showError(error.message);
      }
    } finally {
      if (typeof hideLoading === 'function') hideLoading();
    }
  }

  // 백엔드 API로 가장 가까운 역 찾기
  async fetchNearestStationFromAPI(latitude, longitude) {
    // TODO: 백엔드에 /api/nearest-station 엔드포인트 추가 필요
    // 현재는 클라이언트 사이드에서 간단히 처리

    const stations = window.stations || [];

    // 임시: 하드코딩된 주요 역 좌표 (실제로는 DB에서 가져와야 함)
    const stationCoords = this.getHardcodedStationCoordinates();

    // 좌표 매칭
    const stationsWithCoords = stations.map(station => {
      const coords = stationCoords[station.name];
      return {
        ...station,
        latitude: coords ? coords.lat : null,
        longitude: coords ? coords.lng : null
      };
    }).filter(s => s.latitude && s.longitude);

    if (stationsWithCoords.length === 0) {
      return null;
    }

    const result = this.findNearestStation(
      latitude,
      longitude,
      stationsWithCoords
    );

    return result;
  }

  // 2호선 전체 역 좌표 (map.js와 동기화)
  getHardcodedStationCoordinates() {
    return {
      '시청': { lat: 37.5662, lng: 126.9779 },
      '을지로입구': { lat: 37.5658, lng: 126.9822 },
      '을지로3가': { lat: 37.5662, lng: 126.9914 },
      '을지로4가': { lat: 37.5669, lng: 127.0017 },
      '동대문역사문화공원': { lat: 37.5652, lng: 127.0079 },
      '신당': { lat: 37.5661, lng: 127.0177 },
      '상왕십리': { lat: 37.5658, lng: 127.0294 },
      '왕십리': { lat: 37.5617, lng: 127.0377 },
      '한양대': { lat: 37.5559, lng: 127.0442 },
      '뚝섬': { lat: 37.5467, lng: 127.0472 },
      '성수': { lat: 37.5445, lng: 127.0557 },
      '건대입구': { lat: 37.5401, lng: 127.0695 },
      '구의': { lat: 37.5371, lng: 127.0855 },
      '강변': { lat: 37.5348, lng: 127.0944 },
      '잠실나루': { lat: 37.5202, lng: 127.1020 },
      '잠실': { lat: 37.5133, lng: 127.1000 },
      '잠실새내': { lat: 37.5112, lng: 127.0860 },
      '종합운동장': { lat: 37.5107, lng: 127.0735 },
      '삼성': { lat: 37.5088, lng: 127.0633 },
      '선릉': { lat: 37.5045, lng: 127.0493 },
      '역삼': { lat: 37.5004, lng: 127.0364 },
      '강남': { lat: 37.4979, lng: 127.0276 },
      '교대': { lat: 37.4934, lng: 127.0145 },
      '서초': { lat: 37.4916, lng: 127.0078 },
      '방배': { lat: 37.4814, lng: 126.9976 },
      '사당': { lat: 37.4766, lng: 126.9816 },
      '낙성대': { lat: 37.4768, lng: 126.9636 },
      '서울대입구': { lat: 37.4814, lng: 126.9527 },
      '봉천': { lat: 37.4821, lng: 126.9426 },
      '신림': { lat: 37.4842, lng: 126.9296 },
      '신대방': { lat: 37.4872, lng: 126.9130 },
      '구로디지털단지': { lat: 37.4851, lng: 126.9015 },
      '대림': { lat: 37.4932, lng: 126.8956 },
      '신도림': { lat: 37.5089, lng: 126.8913 },
      '문래': { lat: 37.5178, lng: 126.8950 },
      '영등포구청': { lat: 37.5244, lng: 126.8960 },
      '당산': { lat: 37.5345, lng: 126.9025 },
      '합정': { lat: 37.5494, lng: 126.9139 },
      '홍대입구': { lat: 37.5571, lng: 126.9245 },
      '신촌': { lat: 37.5559, lng: 126.9368 },
      '이대': { lat: 37.5566, lng: 126.9458 },
      '아현': { lat: 37.5573, lng: 126.9567 },
      '충정로': { lat: 37.5598, lng: 126.9637 }
    };
  }

  // 위치 추적 시작 (실시간 업데이트)
  startWatching(callback) {
    if (!this.isAvailable()) {
      console.error('GPS를 지원하지 않는 브라우저입니다');
      return;
    }

    this.watchId = navigator.geolocation.watchPosition(
      (position) => {
        this.currentPosition = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: position.timestamp
        };
        if (callback) callback(this.currentPosition);
      },
      (error) => {
        console.error('GPS 위치 추적 오류:', error);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 30000
      }
    );

    this.enabled = true;
  }

  // 위치 추적 중지
  stopWatching() {
    if (this.watchId !== null) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
      this.enabled = false;
    }
  }
}

// 전역 인스턴스
const geoService = new GeoLocationService();

// UI 통합
function addGPSButton(inputGroupId, stationSelectId) {
  const inputGroup = document.querySelector(`#${inputGroupId} .select-wrapper`);
  if (!inputGroup) return;

  // GPS 버튼이 이미 있으면 추가하지 않음
  if (inputGroup.querySelector('.gps-btn')) return;

  const btn = document.createElement('button');
  btn.className = 'gps-btn';
  btn.type = 'button';
  btn.innerHTML = '📍';
  btn.title = '현재 위치에서 가장 가까운 역';
  btn.onclick = () => geoService.autoSelectNearestStation(stationSelectId);

  inputGroup.appendChild(btn);
}

// 과녁/크로스헤어 SVG 아이콘
const GPS_ICON_SVG = `
<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
  <circle cx="12" cy="12" r="3"/>
  <circle cx="12" cy="12" r="8"/>
  <line x1="12" y1="2" x2="12" y2="6"/>
  <line x1="12" y1="18" x2="12" y2="22"/>
  <line x1="2" y1="12" x2="6" y2="12"/>
  <line x1="18" y1="12" x2="22" y2="12"/>
</svg>`;

// DOM 로드 후 GPS 버튼 추가
document.addEventListener('DOMContentLoaded', () => {
  if (geoService.isAvailable()) {
    // 출발역에만 GPS 버튼 추가 (도착역은 사용자가 직접 선택)
    setTimeout(() => {
      // boarding-search input의 부모 select-wrapper를 직접 찾기
      const boardingInput = document.getElementById('boarding-search');
      if (boardingInput) {
        const wrapper = boardingInput.closest('.select-wrapper');
        if (wrapper && !wrapper.querySelector('.gps-btn')) {
          const btn = document.createElement('button');
          btn.className = 'gps-btn';
          btn.type = 'button';
          btn.innerHTML = GPS_ICON_SVG;
          btn.title = '현재 위치에서 가장 가까운 역 자동 선택';
          btn.onclick = async () => {
            btn.classList.add('loading');
            try {
              await geoService.autoSelectNearestStation('boarding');
            } finally {
              btn.classList.remove('loading');
            }
          };
          wrapper.appendChild(btn);
        }
      }
    }, 500);
  }
});
