# Metropy

[![CI](https://github.com/YujunOh/metropy/actions/workflows/ci.yml/badge.svg)](https://github.com/YujunOh/metropy/actions/workflows/ci.yml)

## 프로젝트 소개

서울 지하철 2호선에서 앉을 수 있는 칸을 추천해주는 웹앱이에요. 공공데이터를 분석해서 각 칸별 착석 확률을 계산하고, 현재 시간과 경로에 맞게 가장 앉기 좋은 칸을 알려줍니다.

## 주요 기능

- **SeatScore 알고리즘**: 각 칸별 착석 확률을 점수로 계산
- **자동 방향 판별**: 순환선에서 최단 경로 자동 계산
- **GPS 기반 역 검색**: 현재 위치에서 가장 가까운 역 찾기
- **한글 검색**: 초성 입력과 유사 역명 추천
- **시간대별 분석**: 출근/점심/퇴근 시간대별 혼잡도 반영
- **PWA 지원**: 오프라인 캐싱, 홈 화면 설치 가능
- **다크/라이트 테마**: 사용자 설정 저장

## 기술 스택

**백엔드**: FastAPI, pandas, numpy, scikit-learn  
**프론트엔드**: Vanilla JavaScript, Chart.js, PWA  
**데이터**: KMA 기상청 API, TMAP Transit API, SK Open API  
**배포**: Render, GitHub Actions

## 실행 방법

```bash
# 저장소 클론
git clone https://github.com/YujunOh/metropy.git
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

# 서버 실행
python run.py
```

http://127.0.0.1:8000 에서 확인하세요.

## 라이선스

MIT License

---

[YujunOh](https://github.com/YujunOh) | [라이브 데모](https://metropy.onrender.com)
