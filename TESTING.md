# 테스트 가이드

## 테스트 실행 방법

### 1. 테스트 패키지 설치

```bash
pip install -r requirements.txt
```

또는 테스트 패키지만 설치:

```bash
pip install pytest pytest-asyncio pytest-cov httpx
```

### 2. 모든 테스트 실행

```bash
pytest
```

### 3. 상세 출력으로 실행

```bash
pytest -v
```

### 4. 특정 테스트 파일만 실행

```bash
# SeatScore 엔진 테스트
pytest tests/test_seatscore.py -v

# API 엔드포인트 테스트
pytest tests/test_api.py -v
```

### 5. 특정 테스트 클래스만 실행

```bash
pytest tests/test_seatscore.py::TestSeatScoreEngine -v
```

### 6. 특정 테스트 함수만 실행

```bash
pytest tests/test_seatscore.py::TestSeatScoreEngine::test_compute_seatscore -v
```

### 7. 코드 커버리지 측정

```bash
pytest --cov=src --cov=web --cov-report=html
```

커버리지 리포트는 `htmlcov/index.html`에서 확인 가능합니다.

### 8. 마커를 사용한 테스트 선택

```bash
# 느린 테스트 제외
pytest -m "not slow"

# 유닛 테스트만 실행
pytest -m unit
```

## 테스트 구조

```
tests/
├── __init__.py           # 테스트 패키지
├── conftest.py          # pytest 설정 및 픽스처
├── test_seatscore.py    # SeatScore 엔진 테스트
└── test_api.py          # API 엔드포인트 테스트
```

## 주요 테스트 케이스

### SeatScore 엔진 테스트

- ✅ 엔진 로딩
- ✅ 시설 가중치 설정
- ✅ 시간대 배율 계산
- ✅ SeatScore 계산
- ✅ 추천 함수
- ✅ 역 이름 정규화
- ✅ 성능 테스트

### API 엔드포인트 테스트

- ✅ 루트 엔드포인트
- ✅ 정적 파일 서빙
- ✅ 역 목록 조회
- ✅ 추천 요청 (정상/비정상)
- ✅ 캘리브레이션 조회/설정
- ✅ 민감도 분석
- ✅ 에러 처리
- ✅ 성능 및 동시성 테스트

## CI/CD 통합

GitHub Actions를 사용한 자동 테스트 예시:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=src --cov=web
```

## 트러블슈팅

### 테스트가 실패하는 경우

1. **데이터 파일 확인**: `data_processed/` 디렉토리에 필요한 파일이 있는지 확인
2. **환경 변수 확인**: `.env` 파일 설정 확인
3. **서버 실행 여부**: 다른 인스턴스가 실행 중인지 확인 (포트 충돌)

### 특정 테스트만 실패하는 경우

```bash
# 실패한 테스트만 재실행
pytest --lf

# 더 상세한 에러 메시지 출력
pytest -vv --tb=long
```

## 테스트 작성 가이드

새로운 기능을 추가할 때는 다음 순서로 테스트를 작성하세요:

1. **유닛 테스트**: 개별 함수/메서드 테스트
2. **통합 테스트**: 여러 컴포넌트 간의 상호작용 테스트
3. **E2E 테스트**: 전체 시스템 흐름 테스트

### 픽스처 사용 예시

```python
def test_example(seatscore_engine, sample_route):
    result = seatscore_engine.recommend(**sample_route)
    assert result["best_car"] >= 1
```

## 성능 벤치마크

목표 성능 지표:

- 추천 계산: < 1초
- API 응답: < 2초
- 동시 요청 처리: 10개 이상

## 참고 자료

- [pytest 공식 문서](https://docs.pytest.org/)
- [FastAPI 테스팅 가이드](https://fastapi.tiangolo.com/tutorial/testing/)
