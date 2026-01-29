# Metropy

서울 2호선에서 어디 타야 앉을 수 있을까?

공공데이터(혼잡도, 하차율, 환승정보 등)를 조합해서 칸별 착석 점수를 계산해주는 웹 서비스입니다.

지하철 타면 항상 서서 가는 게 싫어서 만들었습니다.

## 기능

- 출발역/도착역 넣으면 몇 번째 칸 타야 앉을 확률이 높은지 추천
- GPS로 가까운 역 자동으로 잡아줌
- 시간대별 혼잡도 반영 (출근/퇴근 등)
- 초성 검색 (ㅎㄷ → 홍대입구)
- 다크모드, 즐겨찾기

## 데이터

SK Open API, 서울 열린데이터광장, TMAP Transit 등 10개 소스에서 수집

## 스택

- Python / FastAPI
- 바닐라 JS
- Render 배포

## 실행 방법

```bash
pip install -r requirements.txt
python run.py
```

http://localhost:8000 접속

## 배포

https://metropy.onrender.com
