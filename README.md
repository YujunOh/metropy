# 🚇 Metropy

**서울 지하철 2호선 착석 효용 최적화 의사결정 모델**

어느 칸에 타야 앉을 수 있을까? Metropy는 공공데이터 분석을 통해 이동 중 착석 가능성이 가장 높은 칸을 추천합니다.

## 📋 프로젝트 개요

Metropy는 서울 지하철 2호선의 혼잡도 데이터, 빠른환승 시설 정보, 역간 거리 등을 분석하여 **SeatScore**라는 효용 점수를 계산합니다. 기존 지하철 앱들이 "빠른 하차"에 집중하는 것과 달리, Metropy는 **"이동 중 착석 경험"**을 최적화합니다.

### 주요 기능
- 🎯 출발역/도착역/시간대 기반 최적 탑승 칸 추천
- 📊 칸별 SeatScore 시각화 및 비교
- ⚙️ 하이퍼파라미터 실시간 조정 및 민감도 분석
- 📈 경유역 하차 패턴 및 시설 분포 분석

### 데이터 소스
- 혼잡도 데이터: 316,800건 (서울 열린데이터광장)
- 빠른환승 정보: 450건 (서울교통공사 API)
- 역간 거리: 52개 구간
- 분석 대상: 2호선 43개 역, 10량 편성

## 🚀 빠른 시작

### 1. 설치

```bash
# 저장소 클론
git clone <repository-url>
cd metropy

# 가상환경 생성 (권장)
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 실행

#### 방법 1: 간단한 실행 스크립트 사용
```bash
python run.py
```

#### 방법 2: 직접 서버 실행
```bash
uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
```

서버가 시작되면 브라우저에서 **http://127.0.0.1:8000** 으로 접속하세요!

### 3. 사용법

1. **경로 입력**: 출발역, 도착역, 탑승 시간 선택
2. **추천 확인**: 최적 칸 번호와 SeatScore 확인
3. **상세 분석**: 칸별 점수, 경유역 정보, Benefit/Penalty 분해 확인
4. **파라미터 조정**: 캘리브레이션 페이지에서 모델 가중치 실시간 조정

## 📁 프로젝트 구조

```
metropy/
├── data_raw/               # 원본 데이터
│   ├── fast_exit_line2.json
│   ├── hourly_line2_station_cnt.csv
│   ├── station_master.csv
│   └── interstation_distance_time.csv
├── data_processed/         # 전처리된 데이터
│   ├── congestion_long.csv
│   ├── interstation_distance_processed.csv
│   └── alighting_cache.pkl
├── frontend/               # 프론트엔드 (HTML/CSS/JS)
│   ├── index.html
│   ├── css/style.css
│   └── js/
├── web/                    # FastAPI 백엔드
│   ├── app.py
│   ├── dependencies.py
│   ├── schemas.py
│   └── routers/
├── src/                    # 핵심 로직
│   ├── seatscore.py       # SeatScore 엔진
│   ├── preprocessing.py   # 데이터 전처리
│   └── congestion_model.py # 혼잡도 예측 모델
├── report/                 # 분석 리포트
│   └── final_report.md
├── requirements.txt
└── run.py                  # 실행 스크립트
```

## 🧮 SeatScore 공식

```
SeatScore(c) = Σ[D(s) × T(s→dest) × w(c,s) × α(h)] - β × B(c,h)
```

- **D(s)**: 중간역 s의 하차량
- **T(s→dest)**: 잔여 이동 거리 (km)
- **w(c,s)**: 칸 c의 시설 가중치 (에스컬레이터 1.5, 엘리베이터 1.2, 계단 1.0)
- **α(h)**: 시간대 배율 (출근 1.4, 퇴근 1.3, 주간 1.0, 심야 0.6)
- **β**: 탑승 혼잡 페널티 계수 (기본 0.3)
- **B(c,h)**: 탑승 혼잡도 (중간 칸은 탑승 인원도 많음)

## 🔬 주요 발견

- **3호차**: 10개 시나리오 중 5개에서 1위
- **4호차**: 10개 시나리오 중 3개에서 1위
- **1, 10호차**: 양 끝 칸은 일관되게 최하위
- 중간 칸(3~7호차)은 출구 시설 집중으로 하차가 많지만, 탑승 인원도 많아 트레이드오프 존재

## ✨ 주요 기능

### 🎯 핵심 기능

- **칸별 착석 효용 점수**: SeatScore v2 알고리즘 기반 10개 칸 랭킹
- **실시간 추천**: 출발/도착역, 시간대 기반 최적 칸 추천
- **시각화**: Chart.js 기반 Benefit/Penalty 분석 차트
- **하이퍼파라미터 조정**: 실시간 β, α, w 조정 및 민감도 분석

### 🚀 고급 기능 (v2.0)

- **🔍 초성 검색 + 퍼지 매칭**: 한글 초성 검색 지원, Levenshtein 거리 기반 유사 역명 추천
- **💡 추천 이유 시각화**: 칸 선택 이유, 중간역 기여도, 시설 가중치 효과 상세 설명
- **📍 GPS 자동 입력**: 현재 위치 기반 가장 가까운 역 자동 선택
- **💬 피드백 시스템**: 사용자 만족도 수집 및 통계, JSON 내보내기
- **⚡ 에러 처리 강화**: 자동 재시도, 오프라인 감지, 에러 로깅
- **⭐ 즐겨찾기 & 히스토리**: 자주 사용하는 경로 저장 및 빠른 접근
- **⌨️ 키보드 단축키**: R(추천), H(홈), F(즐겨찾기), /(검색), ?(도움말)
- **📊 사용 통계**: 총 이용 횟수, 자주 사용하는 칸, 피드백 만족도

### 📱 PWA 지원

- **오프라인 지원**: Service Worker 기반 캐싱
- **앱 설치 가능**: 홈 화면에 추가 가능
- **모바일 최적화**: 터치 제스처, 반응형 디자인
- **빠른 로딩**: 정적 파일 캐싱

## 🛠 기술 스택

### 백엔드

- FastAPI: REST API 서버
- uvicorn: ASGI 서버
- pandas, numpy: 데이터 처리
- scikit-learn: 머신러닝 모델

### 프론트엔드

- HTML5/CSS3/JavaScript (Vanilla)
- Chart.js 4.4.1: 데이터 시각화
- PWA: Progressive Web App 지원
- LocalStorage: 클라이언트 데이터 저장

### 데이터
- 서울 열린데이터광장 API
- 서울교통공사 빠른환승 API

## 📊 API 엔드포인트

- `GET /`: 메인 웹 인터페이스
- `GET /api/stations`: 역 목록 조회
- `POST /api/recommend`: 최적 칸 추천
- `GET /api/calibrate`: 현재 파라미터 조회
- `POST /api/calibrate`: 파라미터 업데이트
- `POST /api/calibrate/sensitivity`: 민감도 분석

## 🧪 데이터 전처리

데이터 전처리가 필요한 경우:

```bash
# 전처리 스크립트 실행
python src/preprocessing.py
```

## ⚠️ 제한사항

- 의사결정 지원 모델이며, 예측 모델이 아닙니다
- D(s) 하차량은 역 전체 평균이며 칸별 구분이 아닙니다
- w(c,s)는 시설 구조 기반이며 실제 승객 행동 데이터가 아닙니다
- 점수는 상대적 효용 비교이며 절대적 착석 확률이 아닙니다

## 📝 라이선스

MIT License

## 👨‍💻 작성자

YujunOh (C435247)

## 🔗 관련 문서

- [최종 분석 리포트](report/final_report.md)
- [데이터 전처리 가이드](src/README_preprocessing.md)

---

**Made with ❤️ for better Seoul Metro experience**
