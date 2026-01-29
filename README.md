# Metropy

데이터 분석 프로젝트

## 프로젝트 개요

Metropy는 데이터 분석 및 시각화를 위한 프로젝트입니다.

## 프로젝트 구조

```
metropy/
├── data/
│   ├── raw/          # 원본 데이터
│   └── processed/    # 전처리된 데이터
├── notebooks/        # Jupyter 노트북
├── src/              # 소스 코드
│   ├── data/         # 데이터 처리
│   ├── features/     # 특성 엔지니어링
│   ├── models/       # 모델
│   └── visualization/# 시각화
├── models/           # 저장된 모델
├── outputs/          # 분석 결과
├── plots/            # 생성된 그래프
└── tests/            # 테스트 코드

```

## 설치

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

## 사용법

1. 원본 데이터를 `data/raw/` 폴더에 저장
2. Jupyter Notebook 실행: `jupyter notebook`
3. `notebooks/` 폴더에서 분석 시작

## 주요 라이브러리

- pandas: 데이터 처리
- numpy: 수치 계산
- matplotlib, seaborn: 시각화
- scikit-learn: 머신러닝
- jupyter: 대화형 분석

## 작성자

- YujunOh

## 라이선스

MIT License
