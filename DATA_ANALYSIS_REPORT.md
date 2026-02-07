# 메트로피(Metropy) 데이터 분석 보고서
**생성일**: 2026-01-29
**프로젝트**: 서울 지하철 9호선 착석 효용 분석

---

## 📊 전체 데이터 현황

### ✅ 1. 인코딩 문제 해결 완료

다음 파일들은 **CP949 인코딩**으로 작성되어 있었으며, **UTF-8로 변환 완료**:

| 파일명 | 원본 인코딩 | 행 수 | 열 수 | 내용 |
|--------|------------|-------|-------|------|
| `line9_interstation_distance.csv` | CP949 | 39 | 5 | 9호선 역간 거리 |
| `interStation_distance_time_20240810.csv` | CP949 | 280 | 6 | 전체 노선 역간 거리/소요시간 |
| `station_master.csv` | CP949 | 784 | 5 | 역 마스터 (역ID, 이름, 좌표) |

**변환된 파일**: `*_utf8.csv` 형식으로 저장됨

**컬럼 정보**:
- **line9_interstation_distance.csv**: 철도운영기관명, 선명, 역명, 역간거리, 후행역간거리
- **interStation_distance_time_20240810.csv**: 연번, 호선, 역명, 소요시간, 역간거리(km), 호선별누계(km)
- **station_master.csv**: 역사_ID, 역사명, 호선, 위도, 경도

---

### ✅ 2. 대용량 CSV 파일 분석

#### 📁 `elderly_hourly_station_daily_20231231.csv`
- **크기**: 19.52 MB
- **인코딩**: CP949
- **행 수**: 198,643 rows
- **열 수**: 25 columns
- **내용**: 노인 시간대별 역별 승하차 (2023년 12월 31일)
- **주요 컬럼**:
  ```
  순번, 사용일자, 역번호, 역명, 승하차구분,
  06시간이전까지, 06-07시간대, 07-08시간대, ..., 24시간이후까지
  ```

#### 📁 `hourly_line_station_cnt.csv`
- **크기**: 27.45 MB
- **인코딩**: CP949
- **행 수**: 78,630 rows
- **열 수**: 52 columns
- **내용**: 시간대별 노선-역 승하차 인원 (2025년 11월)
- **주요 컬럼**:
  ```
  사용월, 호선명, 역철도,
  04시-05시 승차인원, 04시-05시 하차인원,
  05시-06시 승차인원, 05시-06시 하차인원,
  ... (시간대별 반복) ...,
  작업일자
  ```
- **특징**: 시간대별로 승차/하차 쌍으로 컬럼 구성

---

### ⚠️ 3. XLSX 파일 (미분석 - Python 환경 문제)

| 파일명 | 크기 | 상태 |
|--------|------|------|
| `congestion_line9_weekday_weekend_station_hour.xlsx` | 15 MB | openpyxl 필요 |
| `line_station_ID.xlsx` | 30 KB | openpyxl 필요 |

**해결방안**:
```bash
# Jupyter notebook에서 pandas로 읽기
import pandas as pd
df = pd.read_excel('파일명.xlsx')
```

---

### ✅ 4. 디렉토리 구조

#### 📂 `congestion_30min/` (혼잡도 30분 단위)
```
20231231.csv       - 413 KB (2023년 12월 31일)
20240630.csv       - 413 KB (2024년  6월 30일)
20241231.csv       - 364 KB (2024년 12월 31일)
20250331.xlsx      - 418 KB (2025년  3월 31일)
```

#### 📂 `daily_station_line_cnt/` (일별 역별 승하차)
```
CARD_SUBWAY_MONTH_202510.csv  - 1.2 MB (2025년 10월)
CARD_SUBWAY_MONTH_202511.csv  - 1.2 MB (2025년 11월)
```

#### 📂 `path_hour_cnt/` (경로별 시간대 통행량)
```
20251215.csv  - 74 MB (2025년 12월 15일)
20251216.csv  - 74 MB (2025년 12월 16일)
```
**⚠️ 주의**: 매우 큰 파일 (각 74MB) - 샘플링 또는 청킹 필요

---

## 🔧 데이터 전처리 권장사항

### 1. 인코딩 통일
```python
# 모든 CSV 파일을 UTF-8로 변환
# 스크립트: scripts/fix_encoding.py 사용
```

### 2. 대용량 파일 처리
```python
# 청킹 방식 읽기
import pandas as pd

chunk_size = 10000
for chunk in pd.read_csv('large_file.csv', chunksize=chunk_size, encoding='cp949'):
    # 처리
    pass

# 또는 필요한 컬럼만 선택
df = pd.read_csv('large_file.csv', usecols=['역명', '시간대', '승차인원'], encoding='cp949')
```

### 3. 시간대 데이터 정규화
- `hourly_line_station_cnt.csv`의 wide format을 long format으로 변환 권장:
  ```python
  df_melted = pd.melt(df,
                      id_vars=['사용월', '호선명', '역철도'],
                      value_vars=['04시-05시 승차인원', '04시-05시 하차인원', ...],
                      var_name='시간대_구분',
                      value_name='인원')
  ```

### 4. 9호선 데이터 필터링
```python
# 9호선만 추출
df_line9 = df[df['호선명'].str.contains('9호선')]
```

---

## 💡 기말과제 활용 전략

### 사용 가능한 핵심 데이터:

1. **혼잡도 데이터**:
   - `congestion_30min/` 폴더의 시계열 데이터
   - 30분 단위 역별 혼잡도

2. **승하차 데이터**:
   - `hourly_line_station_cnt.csv` - 시간대별 승하차
   - `daily_station_line_cnt/` - 일별 집계

3. **역 정보**:
   - `station_master_utf8.csv` - 역 좌표, ID
   - `interStation_distance_time_20240810_utf8.csv` - 역간 거리/시간

4. **9호선 특화**:
   - `line9_interstation_distance_utf8.csv` - 9호선 역간 거리
   - `congestion_line9_weekday_weekend_station_hour.xlsx` - 9호선 혼잡도 (XLSX)

### 분석 파이프라인 제안:

```
1. 데이터 로드 (인코딩 문제 해결)
   ↓
2. 9호선 데이터 필터링
   ↓
3. 시간대별 혼잡도 패턴 분석
   ↓
4. 역별 승하차 규모 추정
   ↓
5. SeatScore 계산
   ↓
6. 칸별 추천 생성
```

---

## 📝 다음 단계 (TODO)

- [ ] Jupyter notebook 생성: `notebooks/01_data_exploration.ipynb`
- [ ] XLSX 파일 pandas로 읽기 (openpyxl 설치 확인)
- [ ] 전처리 파이프라인 스크립트 작성
- [ ] 9호선 데이터셋 통합본 생성
- [ ] EDA (Exploratory Data Analysis) 수행
- [ ] 기말과제 PDF 업데이트

---

## 🛠️ 생성된 도구

1. **scripts/fix_encoding.py** - 인코딩 문제 자동 해결
2. **scripts/analyze_large_files.py** - 대용량 파일 구조 분석
3. **inputs/*_utf8.csv** - UTF-8 변환된 데이터

---

**작성자**: Claude Code
**마지막 업데이트**: 2026-01-29
