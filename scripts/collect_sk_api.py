# -*- coding: utf-8 -*-
"""
SK Open API Smart Data Collector
==================================
Seoul Metro Line 2 차량별 혼잡도/하차율 데이터 수집기.

핵심 전략: 한 번 수집 → 캐시에 저장 → 런타임 API 호출 없이 서비스.

수집 우선순위:
  Phase 1: getOffCarRate (러시아워) - 좌석 추천에 가장 큰 영향
  Phase 2: congestionCar (러시아워) - 탑승 패널티 계산
  Phase 3: getOffCarRate (나머지 시간)
  Phase 4: congestionCar (나머지 시간)
  Phase 5: congestionTrain (선택적)

사용법:
  python scripts/collect_sk_api.py --test            # API 연결 테스트
  python scripts/collect_sk_api.py --status          # 수집 현황 확인
  python scripts/collect_sk_api.py --collect          # 스마트 수집 시작
  python scripts/collect_sk_api.py --collect --limit 100  # 일일 한도 지정
  python scripts/collect_sk_api.py --process          # 캐시 빌드
"""

import json
import time
import pickle
from pathlib import Path
from datetime import datetime, date
import sys

try:
    import requests
except ImportError:
    print("requests 설치 중...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent

# ─── SK Open API 설정 ───────────────────────────────────────
SK_API_KEY = "V4kZORPDLL4tosV1csaYr1lM98hEfT6B1TAjuRx7"
SK_BASE_URL = "https://apis.openapi.sk.com/puzzle/subway/congestion/stat"

HEADERS = {
    "accept": "application/json",
    "appKey": SK_API_KEY,  # 반드시 대문자 K
}

# ─── 2호선 역코드 매핑 (3자리) ──────────────────────────────
LINE2_STATIONS = {
    "시청": "201", "을지로입구": "202", "을지로3가": "203",
    "을지로4가": "204", "동대문역사문화공원": "205", "신당": "206",
    "상왕십리": "207", "왕십리": "208", "한양대": "209",
    "뚝섬": "210", "성수": "211", "건대입구": "212",
    "구의": "213", "강변": "214", "잠실나루": "215",
    "잠실": "216", "잠실새내": "217", "종합운동장": "218",
    "삼성": "219", "선릉": "220", "역삼": "221",
    "강남": "222", "교대": "223", "서초": "224",
    "방배": "225", "사당": "226", "낙성대": "227",
    "서울대입구": "228", "봉천": "229", "신림": "230",
    "신대방": "231", "구로디지털단지": "232", "대림": "233",
    "신도림": "234", "문래": "235", "영등포구청": "236",
    "당산": "237", "합정": "238", "홍대입구": "239",
    "신촌": "240", "이대": "241", "아현": "242",
    "충정로": "243",
}

# 운행 시간 (05시 ~ 23시)
ALL_HOURS = list(range(5, 24))

# 러시아워 (우선 수집)
RUSH_HOURS = [7, 8, 9, 17, 18, 19]
NON_RUSH_HOURS = [h for h in ALL_HOURS if h not in RUSH_HOURS]

# 엔드포인트 정의
ENDPOINTS = {
    "getoff":  ("get-off/stations", "getOffCarRate"),   # 하차율 (최우선)
    "car":     ("car/stations",     "congestionCar"),    # 차량 혼잡도
    "train":   ("train/stations",   "congestionTrain"),  # 열차 혼잡도 (선택)
}

# 진행 상황 파일
PROGRESS_FILE = PROJECT_ROOT / "data_raw" / "sk_api" / "collection_progress.json"
RAW_DATA_DIR = PROJECT_ROOT / "data_raw" / "sk_api"


# ─── 진행 상황 관리 ─────────────────────────────────────────

def load_progress():
    """수집 진행 상황 로드."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "collected": {},  # "endpoint|station|dow|hour" → timestamp
        "errors": {},     # "endpoint|station|dow|hour" → error count
        "daily_log": {},  # "YYYY-MM-DD" → call count
        "total_calls": 0,
        "total_cost_won": 0,
    }


def save_progress(progress):
    """수집 진행 상황 저장."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def is_collected(progress, endpoint, station, dow, hour):
    """이미 수집된 데이터인지 확인."""
    key = f"{endpoint}|{station}|{dow}|{hour}"
    return key in progress["collected"]


def mark_collected(progress, endpoint, station, dow, hour):
    """수집 완료로 표시."""
    key = f"{endpoint}|{station}|{dow}|{hour}"
    progress["collected"][key] = datetime.now().isoformat()
    today = date.today().isoformat()
    progress["daily_log"][today] = progress["daily_log"].get(today, 0) + 1
    progress["total_calls"] += 1


def get_today_calls(progress):
    """오늘 호출 수 확인."""
    today = date.today().isoformat()
    return progress["daily_log"].get(today, 0)


# ─── API 호출 함수 ──────────────────────────────────────────

def fetch_endpoint(endpoint_key, station_code, dow="MON", hh="08"):
    """
    범용 API 호출 함수.
    Returns: (data_dict, status_code) or (None, status_code)
    """
    path, _ = ENDPOINTS[endpoint_key]
    url = f"{SK_BASE_URL}/{path}/{station_code}"
    params = {"dow": dow, "hh": str(hh).zfill(2)}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json(), 200
        elif resp.status_code == 429:
            return None, 429  # 한도 초과
        elif resp.status_code == 404:
            return None, 404  # 데이터 없음
        else:
            return None, resp.status_code
    except requests.exceptions.Timeout:
        return None, -1
    except Exception as e:
        return None, -2


# ─── 수집 전략 ───────────────────────────────────────────────

def build_collection_plan(dow="MON", include_train=False):
    """
    우선순위 기반 수집 계획 생성.

    우선순위:
      1. getoff + 러시아워 (좌석 추천 핵심)
      2. car + 러시아워 (탑승 패널티)
      3. getoff + 나머지 시간
      4. car + 나머지 시간
      5. train (선택적)
    """
    plan = []
    stations = list(LINE2_STATIONS.keys())

    # Phase 1: getoff × 러시아워
    for station in stations:
        for hour in RUSH_HOURS:
            plan.append(("getoff", station, dow, hour, "P1-getoff-rush"))

    # Phase 2: car × 러시아워
    for station in stations:
        for hour in RUSH_HOURS:
            plan.append(("car", station, dow, hour, "P2-car-rush"))

    # Phase 3: getoff × 나머지 시간
    for station in stations:
        for hour in NON_RUSH_HOURS:
            plan.append(("getoff", station, dow, hour, "P3-getoff-rest"))

    # Phase 4: car × 나머지 시간
    for station in stations:
        for hour in NON_RUSH_HOURS:
            plan.append(("car", station, dow, hour, "P4-car-rest"))

    # Phase 5: train (선택적)
    if include_train:
        for station in stations:
            for hour in ALL_HOURS:
                plan.append(("train", station, dow, hour, "P5-train"))

    return plan


def smart_collect(daily_limit=100, delay=1.0, dow="MON", include_train=False,
                  cost_per_call=33):
    """
    스마트 배치 수집.

    - 우선순위 순서대로 수집
    - 이미 수집된 데이터는 건너뜀
    - 일일 한도 도달 시 자동 중단
    - 429 에러 시 자동 중단
    - 진행 상황 실시간 저장

    Args:
        daily_limit: 일일 API 호출 한도 (Basic=100, Hackathon≈100/day equiv)
        delay: API 호출 간 대기 시간 (초)
        dow: 요일 (기본 MON=평일 대표)
        include_train: train 엔드포인트도 수집할지
        cost_per_call: 건당 비용 (원) - Basic=33, Hackathon=11
    """
    progress = load_progress()
    plan = build_collection_plan(dow, include_train)

    # 이미 수집된 항목 필터링
    remaining = [
        (ep, st, d, h, phase)
        for ep, st, d, h, phase in plan
        if not is_collected(progress, ep, st, d, h)
    ]

    today_calls = get_today_calls(progress)
    budget_remaining = daily_limit - today_calls

    print(f"\n{'='*60}")
    print(f"  SK API 스마트 수집기")
    print(f"{'='*60}")
    print(f"  전체 계획:     {len(plan)} 건")
    print(f"  수집 완료:     {len(plan) - len(remaining)} 건")
    print(f"  남은 수집:     {len(remaining)} 건")
    print(f"  오늘 호출:     {today_calls} / {daily_limit}")
    print(f"  오늘 가능:     {budget_remaining} 건")
    print(f"  예상 비용:     {min(budget_remaining, len(remaining)) * cost_per_call:,}원")
    print(f"  전체 완료까지: ~{max(1, len(remaining) // daily_limit)} 일")
    print(f"  건당 비용:     {cost_per_call}원")
    print(f"{'='*60}\n")

    if not remaining:
        print("[OK] 모든 데이터가 이미 수집되었습니다!")
        return progress

    if budget_remaining <= 0:
        print("[STOP] 오늘 일일 한도에 도달했습니다. 내일 다시 실행하세요.")
        return progress

    # 수집 시작
    collected_this_session = 0
    current_phase = None
    session_errors = 0
    raw_results = _load_raw_results()

    for ep, station, d, hour, phase in remaining:
        # 일일 한도 확인
        if collected_this_session >= budget_remaining:
            print(f"\n[STOP] 일일 한도 도달 ({daily_limit}건). 내일 다시 실행하세요.")
            break

        # Phase 변경 알림
        if phase != current_phase:
            current_phase = phase
            print(f"\n--- {phase} ---")

        # API 호출
        code = LINE2_STATIONS[station]
        data, status = fetch_endpoint(ep, code, d, str(hour).zfill(2))

        if status == 429:
            print(f"\n[STOP] 429 한도 초과! 진행 상황이 저장되었습니다.")
            print(f"  수집된 데이터: {collected_this_session}건")
            save_progress(progress)
            _save_raw_results(raw_results)
            return progress

        if status == 200 and data:
            mark_collected(progress, ep, station, d, hour)
            collected_this_session += 1

            # raw 결과 저장
            result_key = f"{ep}|{station}|{d}|{hour}"
            raw_results[result_key] = data

            # 진행 상황 표시
            total_done = len(progress["collected"])
            pct = total_done / len(plan) * 100
            if collected_this_session % 10 == 0:
                print(f"  [{pct:5.1f}%] {ep:6s} | {station:10s} | {d} {hour:02d}시 "
                      f"| 오늘 {collected_this_session}건 | 전체 {total_done}/{len(plan)}")
        else:
            session_errors += 1
            err_key = f"{ep}|{station}|{d}|{hour}"
            progress["errors"][err_key] = progress["errors"].get(err_key, 0) + 1

            if session_errors > 10:
                print(f"\n[WARN] 에러가 {session_errors}건 누적되었습니다.")

        # 10건마다 중간 저장
        if collected_this_session % 10 == 0 and collected_this_session > 0:
            save_progress(progress)
            _save_raw_results(raw_results)

        time.sleep(delay)

    # 최종 저장
    save_progress(progress)
    _save_raw_results(raw_results)

    progress["total_cost_won"] = progress["total_calls"] * cost_per_call

    print(f"\n{'='*60}")
    print(f"  세션 완료")
    print(f"{'='*60}")
    print(f"  이번 세션:   {collected_this_session} 건 수집")
    print(f"  세션 에러:   {session_errors} 건")
    print(f"  누적 수집:   {len(progress['collected'])} / {len(plan)} 건")
    print(f"  누적 비용:   약 {progress['total_cost_won']:,}원")
    print(f"{'='*60}")

    save_progress(progress)
    return progress


# ─── Raw 결과 저장/로드 ─────────────────────────────────────

def _load_raw_results():
    """기존 raw 결과 로드."""
    raw_path = RAW_DATA_DIR / "raw_results.json"
    if raw_path.exists():
        with open(raw_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_raw_results(results):
    """Raw 결과 저장."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DATA_DIR / "raw_results.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, default=str)


# ─── 데이터 처리 (Raw → 캐시) ───────────────────────────────

def process_to_caches():
    """
    수집된 Raw 데이터를 SeatScore용 pickle 캐시로 변환.

    생성 파일:
      - car_congestion_cache.pkl: (station, hour, dow) → [10 values]
      - getoff_rate_cache.pkl:    (station, hour, dow) → [10 values]
      - train_congestion_cache.pkl: (station, hour, dow) → float
    """
    raw_results = _load_raw_results()
    if not raw_results:
        print("[ERROR] Raw 데이터가 없습니다. --collect 먼저 실행하세요.")
        return

    processed_dir = PROJECT_ROOT / "data_processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    car_cache = {}
    getoff_cache = {}
    train_cache = {}

    for key, data in raw_results.items():
        parts = key.split("|")
        if len(parts) != 4:
            continue
        ep, station, dow, hour = parts
        hour = int(hour)

        if ep == "car":
            values = _extract_car_values(data, "congestionCar")
            if values and len(values) == 10:
                car_cache[(station, hour, dow)] = values

        elif ep == "getoff":
            values = _extract_car_values(data, "getOffCarRate")
            if values and len(values) == 10:
                getoff_cache[(station, hour, dow)] = values

        elif ep == "train":
            val = _extract_train_value(data)
            if val is not None:
                train_cache[(station, hour, dow)] = val

    # 저장
    if car_cache:
        with open(processed_dir / "car_congestion_cache.pkl", "wb") as f:
            pickle.dump(car_cache, f)
        print(f"[OK] car_congestion_cache.pkl: {len(car_cache)} entries")

    if getoff_cache:
        with open(processed_dir / "getoff_rate_cache.pkl", "wb") as f:
            pickle.dump(getoff_cache, f)
        print(f"[OK] getoff_rate_cache.pkl: {len(getoff_cache)} entries")

    if train_cache:
        with open(processed_dir / "train_congestion_cache.pkl", "wb") as f:
            pickle.dump(train_cache, f)
        print(f"[OK] train_congestion_cache.pkl: {len(train_cache)} entries")

    total = len(car_cache) + len(getoff_cache) + len(train_cache)
    print(f"\n전체 캐시: {total} entries (car={len(car_cache)}, "
          f"getoff={len(getoff_cache)}, train={len(train_cache)})")

    # 커버리지 통계
    all_stations = set(LINE2_STATIONS.keys())
    for cache_name, cache in [("getoff", getoff_cache), ("car", car_cache)]:
        stations_with_data = set(s for s, h, d in cache.keys())
        coverage = len(stations_with_data) / len(all_stations) * 100
        hours_per_station = len(cache) / max(len(stations_with_data), 1)
        print(f"  {cache_name}: {len(stations_with_data)}/{len(all_stations)}역 "
              f"({coverage:.0f}%), 역당 ~{hours_per_station:.0f}시간대")


def _extract_car_values(data, key_hint="congestionCar"):
    """
    API 응답에서 10개 차량 값 추출.

    실제 응답 구조:
    {
      "contents": {
        "stat": [
          {
            "updnLine": 1,  // 방향
            "data": [
              {"dow": "MON", "hh": "08", "mm": "00",
               "getOffCarRate": [7, 10, 10, 15, 12, 11, 11, 9, 8, 7]},
              {"dow": "MON", "hh": "08", "mm": "10", ...},
              ...
            ]
          }
        ]
      }
    }
    """
    if not data or not isinstance(data, dict):
        return None

    if "contents" not in data:
        return None

    contents = data["contents"]
    if "stat" not in contents:
        return None

    stats = contents["stat"]
    if not isinstance(stats, list) or not stats:
        return None

    all_values = []

    for stat_entry in stats:
        data_list = stat_entry.get("data")
        if not isinstance(data_list, list):
            # data가 dict인 이전 형식도 지원
            if isinstance(data_list, dict):
                val = data_list.get(key_hint)
                if val:
                    parsed = _parse_car_array(val)
                    if parsed:
                        all_values.append(parsed)
            continue

        # data가 list인 경우 (10분 간격 측정값 리스트)
        for measurement in data_list:
            if not isinstance(measurement, dict):
                continue
            val = measurement.get(key_hint)
            if val is not None:
                parsed = _parse_car_array(val)
                if parsed:
                    all_values.append(parsed)

    if all_values:
        # 모든 10분 간격의 평균
        return np.array(all_values).mean(axis=0).tolist()

    return None


def _parse_car_array(val):
    """차량별 값을 파싱 (리스트 또는 파이프 구분 문자열)."""
    if isinstance(val, list) and len(val) == 10:
        try:
            return [float(x) for x in val]
        except (ValueError, TypeError):
            return None
    elif isinstance(val, str) and "|" in val:
        parts = [float(x) for x in val.split("|") if x]
        if len(parts) == 10:
            return parts
    return None


def _extract_train_value(data):
    """API 응답에서 열차 혼잡도 값 추출."""
    if not data or not isinstance(data, dict):
        return None

    if "contents" not in data:
        return None

    contents = data["contents"]
    if "stat" not in contents:
        return None

    stats = contents["stat"]
    if not isinstance(stats, list):
        return None

    values = []
    for stat_entry in stats:
        data_list = stat_entry.get("data")
        if isinstance(data_list, list):
            for measurement in data_list:
                if isinstance(measurement, dict):
                    val = measurement.get("congestionTrain")
                    if val is not None:
                        try:
                            values.append(float(val))
                        except (ValueError, TypeError):
                            pass
        elif isinstance(data_list, dict):
            val = data_list.get("congestionTrain")
            if val is not None:
                try:
                    values.append(float(val))
                except (ValueError, TypeError):
                    pass

    return float(np.mean(values)) if values else None


# ─── 상태 확인 ───────────────────────────────────────────────

def show_status():
    """수집 현황 표시."""
    progress = load_progress()
    plan_full = build_collection_plan("MON", include_train=True)
    plan_core = build_collection_plan("MON", include_train=False)

    print(f"\n{'='*60}")
    print(f"  SK API 수집 현황")
    print(f"{'='*60}")
    print(f"  누적 호출:     {progress['total_calls']} 건")
    print(f"  수집 완료:     {len(progress['collected'])} 건")
    print(f"  에러 기록:     {len(progress['errors'])} 건")

    today = date.today().isoformat()
    today_calls = progress["daily_log"].get(today, 0)
    print(f"  오늘 호출:     {today_calls} 건")
    print()

    # Phase별 현황
    phases = {
        "P1-getoff-rush": 0, "P2-car-rush": 0,
        "P3-getoff-rest": 0, "P4-car-rest": 0,
        "P5-train": 0,
    }
    phase_totals = {k: 0 for k in phases}

    for ep, st, d, h, phase in plan_full:
        phase_totals[phase] = phase_totals.get(phase, 0) + 1
        if is_collected(progress, ep, st, d, h):
            phases[phase] = phases.get(phase, 0) + 1

    print("  Phase별 진행:")
    for phase, done in phases.items():
        total = phase_totals[phase]
        pct = done / total * 100 if total > 0 else 0
        bar = "#" * int(pct / 5) + "-" * (20 - int(pct / 5))
        print(f"    {phase:20s} [{bar}] {done:4d}/{total:4d} ({pct:.0f}%)")

    # 코어(getoff+car) 진행률
    core_total = len(plan_core)
    core_done = sum(1 for ep, st, d, h, _ in plan_core
                    if is_collected(progress, ep, st, d, h))
    print(f"\n  코어 데이터:   {core_done}/{core_total} "
          f"({core_done/core_total*100:.1f}%)")

    # 일별 수집 내역
    if progress["daily_log"]:
        print(f"\n  일별 수집 내역:")
        for day, count in sorted(progress["daily_log"].items())[-7:]:
            print(f"    {day}: {count}건")

    print(f"{'='*60}")


# ─── 출구 통계 수집 ──────────────────────────────────────────

EXIT_STAT_URL = "https://apis.openapi.sk.com/puzzle/subway/exit/stat/dow/stations"


def collect_exit_stats(delay=1.0):
    """
    전 역 출구 통행자 수 수집 (요일별).
    각 역당 1건 호출 → 모든 출구 × 모든 요일 데이터 반환.
    43역 = 43건.
    """
    progress = load_progress()
    raw_results = _load_raw_results()

    print(f"\n{'='*60}")
    print(f"  출구 통계 수집 (요일별)")
    print(f"{'='*60}")

    collected = 0
    for station, code in LINE2_STATIONS.items():
        key = f"exit_dow|{station}|ALL|0"
        if key in progress["collected"]:
            continue

        url = f"{EXIT_STAT_URL}/{code}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                raw_results[key] = data
                progress["collected"][key] = datetime.now().isoformat()
                today = date.today().isoformat()
                progress["daily_log"][today] = progress["daily_log"].get(today, 0) + 1
                progress["total_calls"] += 1
                collected += 1
                print(f"  [OK] {station} ({code}): {len(data.get('contents', {}).get('stat', []))} entries")
            elif resp.status_code == 429:
                print(f"  [STOP] 429 한도 초과!")
                break
            else:
                print(f"  [FAIL] {station}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [ERR] {station}: {e}")

        if collected % 5 == 0 and collected > 0:
            save_progress(progress)
            _save_raw_results(raw_results)

        time.sleep(delay)

    save_progress(progress)
    _save_raw_results(raw_results)
    print(f"\n  출구 통계 수집 완료: {collected}건")
    return collected


def process_exit_stats():
    """
    출구 통계 데이터를 캐시로 변환.

    출구 번호 → 차량 번호 매핑은 fast_exit 데이터와 연동.
    결과: exit_traffic_cache.pkl
        (station, dow) → {exit_no: user_count}
    """
    raw_results = _load_raw_results()
    exit_cache = {}

    for key, data in raw_results.items():
        if not key.startswith("exit_dow|"):
            continue

        station = key.split("|")[1]
        if not isinstance(data, dict) or "contents" not in data:
            continue

        stat = data["contents"].get("stat", [])
        for entry in stat:
            dow = entry.get("dow", "MON")
            exit_no = entry.get("exit", "0")
            count = entry.get("userCount", 0)

            cache_key = (station, dow)
            if cache_key not in exit_cache:
                exit_cache[cache_key] = {}
            exit_cache[cache_key][exit_no] = count

    if exit_cache:
        processed_dir = PROJECT_ROOT / "data_processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        with open(processed_dir / "exit_traffic_cache.pkl", "wb") as f:
            pickle.dump(exit_cache, f)
        print(f"[OK] exit_traffic_cache.pkl: {len(exit_cache)} entries")

        # 통계
        stations_with_data = set(s for s, d in exit_cache.keys())
        print(f"  {len(stations_with_data)}/{len(LINE2_STATIONS)}역 "
              f"({len(stations_with_data)/len(LINE2_STATIONS)*100:.0f}%)")
    else:
        print("[WARN] 출구 통계 데이터가 없습니다.")


# ─── 테스트 ──────────────────────────────────────────────────

def test_connection():
    """API 연결 테스트 (최소 호출: 1건)."""
    print("\n=== SK API 연결 테스트 ===\n")

    # 강남역 1건만 테스트
    data, status = fetch_endpoint("getoff", "222", "MON", "08")

    if status == 200 and data:
        print(f"[OK] 연결 성공! (HTTP {status})")
        if "contents" in data:
            c = data["contents"]
            print(f"  역명: {c.get('stationName', '?')}")
            print(f"  노선: {c.get('subwayLine', '?')}")
            stat = c.get("stat", [])
            print(f"  데이터 구간: {len(stat)}개")
            if stat:
                first = stat[0]
                print(f"  첫 구간: {first.get('startTime', '?')}~{first.get('endTime', '?')}")
                d = first.get("data", {})
                if isinstance(d, dict):
                    for k, v in list(d.items())[:3]:
                        val_preview = str(v)[:60]
                        print(f"  {k}: {val_preview}")
                elif isinstance(d, list) and d:
                    # data가 리스트인 경우 첫 항목 표시
                    item = d[0] if isinstance(d[0], dict) else {"value": d[0]}
                    for k, v in list(item.items())[:3]:
                        val_preview = str(v)[:60]
                        print(f"  {k}: {val_preview}")
        return True
    elif status == 429:
        print(f"[LIMIT] 한도 초과 (429). 내일 다시 시도하세요.")
        return False
    else:
        print(f"[FAIL] HTTP {status}")
        if data:
            print(f"  응답: {json.dumps(data, ensure_ascii=False, default=str)[:200]}")
        return False


# ─── 메인 ────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="SK Open API 스마트 데이터 수집기",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python scripts/collect_sk_api.py --test               # 연결 테스트 (1건)
  python scripts/collect_sk_api.py --status              # 수집 현황
  python scripts/collect_sk_api.py --collect             # 수집 시작 (기본 100건/일)
  python scripts/collect_sk_api.py --collect --limit 50  # 50건만 수집
  python scripts/collect_sk_api.py --collect --plan hackathon  # 해커톤 요금제
  python scripts/collect_sk_api.py --process             # 캐시 빌드
        """,
    )
    parser.add_argument("--test", action="store_true",
                        help="API 연결 테스트 (1건만 호출)")
    parser.add_argument("--status", action="store_true",
                        help="수집 현황 확인")
    parser.add_argument("--collect", action="store_true",
                        help="스마트 수집 시작")
    parser.add_argument("--process", action="store_true",
                        help="수집된 데이터를 캐시로 변환")
    parser.add_argument("--limit", type=int, default=None,
                        help="일일 호출 한도 (기본: 요금제에 따라)")
    parser.add_argument("--plan", type=str, default="basic",
                        choices=["basic", "hackathon"],
                        help="요금제 (basic=33원/건, hackathon=11원/건)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="호출 간 대기 (초, 기본 1.0)")
    parser.add_argument("--train", action="store_true",
                        help="train 엔드포인트도 수집")
    parser.add_argument("--exit-stats", action="store_true",
                        help="출구 통계 수집 (43건)")
    parser.add_argument("--dow", type=str, default="MON",
                        help="요일 (기본 MON)")

    args = parser.parse_args()

    # 요금제별 기본값
    plan_config = {
        "basic":     {"limit": 100, "cost": 33},
        "hackathon": {"limit": 100, "cost": 11},  # 월 3000건 / 30일 ≈ 100건/일
    }
    config = plan_config[args.plan]

    if args.test:
        test_connection()
    elif args.status:
        show_status()
    elif args.exit_stats:
        collect_exit_stats(delay=args.delay)
        process_exit_stats()
    elif args.collect:
        limit = args.limit or config["limit"]
        smart_collect(
            daily_limit=limit,
            delay=args.delay,
            dow=args.dow,
            include_train=args.train,
            cost_per_call=config["cost"],
        )
    elif args.process:
        process_to_caches()
        process_exit_stats()  # exit stats도 함께 처리
    else:
        parser.print_help()
        print("\n--- 현재 상태 ---")
        show_status()
