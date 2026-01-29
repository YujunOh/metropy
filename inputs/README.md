# Inputs 폴더

이 폴더는 사용자 입력 파일을 저장하는 곳입니다.

## 용도

- 분석할 원본 데이터 파일
- 설정 파일
- 외부에서 가져온 데이터
- 테스트용 샘플 데이터

## 예시

```
inputs/
├── sample_data.csv
├── config.json
├── user_queries.txt
└── README.md
```

## 사용 방법

1. 분석하고 싶은 파일을 이 폴더에 넣기
2. Jupyter Notebook에서 불러오기:
   ```python
   import pandas as pd
   df = pd.read_csv('../inputs/sample_data.csv')
   ```
