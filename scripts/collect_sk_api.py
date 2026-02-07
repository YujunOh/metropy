# -*- coding: utf-8 -*-
"""
SK Open API Data Collector
==========================
Fetches car-level congestion and alighting rate data from SK Open API
for Seoul Metro Line 2 stations.

Endpoints:
  1. congestionCar  - Per-car congestion (10 cars)
  2. getOffCarRate   - Per-car alighting rate distribution
  3. congestionTrain - Overall train congestion

These data transform SeatScore from estimation-based to measurement-based:
  - congestionCar  → replaces B(c,h) boarding penalty
  - getOffCarRate  → replaces w(c,s) facility weight
  - congestionTrain → calibrates α(h) time multiplier
"""

import json
import time
import pickle
from pathlib import Path
from datetime import datetime
import sys

try:
    import requests
except ImportError:
    print("Installing requests...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

import numpy as np

PROJECT_ROOT = Path(__file__).parent.parent

# SK Open API Configuration
SK_API_KEY = "V4kZORPDLL4tosV1csaYr1lM98hEfT6B1TAjuRx7"
SK_BASE_URL = "https://apis.openapi.sk.com/puzzle/subway/congestion/stat"

HEADERS = {
    "accept": "application/json",
    "Content-Type": "application/json",
    "appkey": SK_API_KEY,
}

# Line 2 Station Code Mapping
# SK API uses station codes from Seoul Metro numbering
# Format: 4-digit string "LLSS" where LL=line, SS=station sequence
LINE2_STATIONS = {
    "시청":           "0201",
    "을지로입구":     "0202",
    "을지로3가":      "0203",
    "을지로4가":      "0204",
    "동대문역사문화공원": "0205",
    "신당":           "0206",
    "상왕십리":       "0207",
    "왕십리":         "0208",
    "한양대":         "0209",
    "뚝섬":           "0210",
    "성수":           "0211",
    "건대입구":       "0212",
    "구의":           "0213",
    "강변":           "0214",
    "잠실나루":       "0215",
    "잠실":           "0216",
    "잠실새내":       "0217",
    "종합운동장":     "0218",
    "삼성":           "0219",
    "선릉":           "0220",
    "역삼":           "0221",
    "강남":           "0222",
    "교대":           "0223",
    "서초":           "0224",
    "방배":           "0225",
    "사당":           "0226",
    "낙성대":         "0227",
    "서울대입구":     "0228",
    "봉천":           "0229",
    "신림":           "0230",
    "신대방":         "0231",
    "구로디지털단지": "0232",
    "대림":           "0233",
    "신도림":         "0234",
    "문래":           "0235",
    "영등포구청":     "0236",
    "당산":           "0237",
    "합정":           "0238",
    "홍대입구":       "0239",
    "신촌":           "0240",
    "이대":           "0241",
    "아현":           "0242",
    "충정로":         "0243",
}

# Day of week mapping
DOW_MAP = {
    0: "MON", 1: "TUE", 2: "WED", 3: "THU",
    4: "FRI", 5: "SAT", 6: "SUN",
}

HOURS = list(range(5, 24))  # 05 ~ 23


def fetch_car_congestion(station_code, dow="MON", hh="08"):
    """
    Fetch per-car congestion for a station.

    GET /puzzle/subway/congestion/stat/car/stations/{stationCode}
    Returns array of 10 congestion values (one per car).
    """
    url = f"{SK_BASE_URL}/car/stations/{station_code}"
    params = {"dow": dow, "hh": str(hh).zfill(2)}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data
        elif resp.status_code == 404:
            return None
        else:
            print(f"  [car] {station_code} {dow} {hh}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [car] {station_code} {dow} {hh}: Error {e}")
        return None


def fetch_getoff_car_rate(station_code, dow="MON", hh="08"):
    """
    Fetch per-car alighting rate for a station.

    GET /puzzle/subway/congestion/stat/get-off/stations/{stationCode}
    Returns array of 10 alighting rate values (one per car).
    """
    url = f"{SK_BASE_URL}/get-off/stations/{station_code}"
    params = {"dow": dow, "hh": str(hh).zfill(2)}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data
        elif resp.status_code == 404:
            return None
        else:
            print(f"  [getoff] {station_code} {dow} {hh}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [getoff] {station_code} {dow} {hh}: Error {e}")
        return None


def fetch_train_congestion(station_code, dow="MON", hh="08"):
    """
    Fetch overall train congestion for a station.

    GET /puzzle/subway/congestion/stat/train/stations/{stationCode}
    Returns single congestion value for the train.
    """
    url = f"{SK_BASE_URL}/train/stations/{station_code}"
    params = {"dow": dow, "hh": str(hh).zfill(2)}

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return data
        elif resp.status_code == 404:
            return None
        else:
            print(f"  [train] {station_code} {dow} {hh}: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"  [train] {station_code} {dow} {hh}: Error {e}")
        return None


def test_api_connection():
    """Test API with a known station to verify connectivity and code format."""
    print("=== Testing SK Open API Connection ===")
    test_station = "0222"  # 강남
    test_name = "강남"

    for endpoint_name, fetch_fn in [
        ("congestionCar", fetch_car_congestion),
        ("getOffCarRate", fetch_getoff_car_rate),
        ("congestionTrain", fetch_train_congestion),
    ]:
        result = fetch_fn(test_station, "MON", "08")
        if result:
            print(f"  {endpoint_name}: OK")
            print(f"    Response keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            # Print first few values
            if isinstance(result, dict):
                for key, val in list(result.items())[:5]:
                    print(f"    {key}: {val}")
        else:
            print(f"  {endpoint_name}: FAILED (station code {test_station} may be wrong)")

    # If all failed, try alternative code formats
    print("\n--- Trying alternative station code formats ---")
    alt_codes = ["222", "0222", "2222", "1002000222", "201"]

    for code in alt_codes:
        result = fetch_car_congestion(code, "MON", "08")
        if result:
            print(f"  Code format '{code}' WORKS!")
            return code
        else:
            print(f"  Code format '{code}': no data")
        time.sleep(0.3)

    return None


def collect_all_data(
    stations=None,
    days=None,
    hours=None,
    output_dir=None,
    delay=0.3,
):
    """
    Collect data for all stations, days, and hours.

    Args:
        stations: Dict of {name: code}. Default: all Line 2 stations.
        days: List of day codes. Default: ['MON', 'SAT', 'SUN']
        hours: List of hours. Default: 5-23
        output_dir: Directory to save results.
        delay: Delay between API calls (seconds).
    """
    if stations is None:
        stations = LINE2_STATIONS
    if days is None:
        days = ["MON", "SAT", "SUN"]  # Weekday + Weekend representative
    if hours is None:
        hours = HOURS
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data_raw" / "sk_api"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_calls = len(stations) * len(days) * len(hours) * 3  # 3 endpoints
    print(f"\n{'='*60}")
    print(f"COLLECTING SK OPEN API DATA")
    print(f"{'='*60}")
    print(f"Stations: {len(stations)}")
    print(f"Days: {days}")
    print(f"Hours: {len(hours)} ({min(hours)}-{max(hours)})")
    print(f"Total API calls: ~{total_calls}")
    print(f"Estimated time: ~{total_calls * delay / 60:.1f} minutes")

    # Data storage
    car_congestion_data = []
    getoff_rate_data = []
    train_congestion_data = []
    call_count = 0
    error_count = 0

    for station_name, station_code in stations.items():
        print(f"\n--- {station_name} ({station_code}) ---")

        for dow in days:
            for hour in hours:
                hh = str(hour).zfill(2)

                # 1. Car congestion
                result = fetch_car_congestion(station_code, dow, hh)
                call_count += 1
                if result:
                    car_congestion_data.append({
                        "station": station_name,
                        "station_code": station_code,
                        "dow": dow,
                        "hour": hour,
                        "data": result,
                    })
                else:
                    error_count += 1

                time.sleep(delay)

                # 2. Get-off car rate
                result = fetch_getoff_car_rate(station_code, dow, hh)
                call_count += 1
                if result:
                    getoff_rate_data.append({
                        "station": station_name,
                        "station_code": station_code,
                        "dow": dow,
                        "hour": hour,
                        "data": result,
                    })
                else:
                    error_count += 1

                time.sleep(delay)

                # 3. Train congestion
                result = fetch_train_congestion(station_code, dow, hh)
                call_count += 1
                if result:
                    train_congestion_data.append({
                        "station": station_name,
                        "station_code": station_code,
                        "dow": dow,
                        "hour": hour,
                        "data": result,
                    })
                else:
                    error_count += 1

                time.sleep(delay)

                # Progress
                if call_count % 50 == 0:
                    print(f"  Progress: {call_count}/{total_calls} calls "
                          f"({error_count} errors)")

        # Save intermediate results per station
        _save_intermediate(output_dir, station_name,
                          car_congestion_data, getoff_rate_data, train_congestion_data)

    # Save final results
    print(f"\n{'='*60}")
    print(f"COLLECTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total calls: {call_count}")
    print(f"Errors: {error_count}")
    print(f"Car congestion records: {len(car_congestion_data)}")
    print(f"Get-off rate records: {len(getoff_rate_data)}")
    print(f"Train congestion records: {len(train_congestion_data)}")

    # Save all data
    save_all_data(output_dir, car_congestion_data, getoff_rate_data, train_congestion_data)

    return car_congestion_data, getoff_rate_data, train_congestion_data


def _save_intermediate(output_dir, station_name, car_data, getoff_data, train_data):
    """Save intermediate results during collection."""
    pass  # Saves happen at the end for simplicity


def save_all_data(output_dir, car_data, getoff_data, train_data):
    """Save all collected data to JSON and processed pickle files."""
    output_dir = Path(output_dir)

    # Raw JSON
    with open(output_dir / "car_congestion_raw.json", "w", encoding="utf-8") as f:
        json.dump(car_data, f, ensure_ascii=False, indent=2, default=str)

    with open(output_dir / "getoff_rate_raw.json", "w", encoding="utf-8") as f:
        json.dump(getoff_data, f, ensure_ascii=False, indent=2, default=str)

    with open(output_dir / "train_congestion_raw.json", "w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2, default=str)

    print(f"Raw data saved to: {output_dir}")

    # Process into lookup caches
    process_sk_data(output_dir)


def process_sk_data(data_dir):
    """
    Process raw SK API data into lookup caches for SeatScore.

    Creates:
      - car_congestion_cache.pkl: (station, hour, dow) → [10 car congestion values]
      - getoff_rate_cache.pkl: (station, hour, dow) → [10 car alighting rates]
      - train_congestion_cache.pkl: (station, hour, dow) → train congestion value
    """
    data_dir = Path(data_dir)
    processed_dir = PROJECT_ROOT / "data_processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    # Car congestion
    car_path = data_dir / "car_congestion_raw.json"
    if car_path.exists():
        with open(car_path, "r", encoding="utf-8") as f:
            car_data = json.load(f)

        car_cache = {}
        for entry in car_data:
            station = entry["station"]
            hour = entry["hour"]
            dow = entry["dow"]
            data = entry["data"]

            # Extract car congestion array
            # API response structure varies; handle common formats
            car_values = _extract_car_values(data, "congestionCar")
            if car_values:
                car_cache[(station, hour, dow)] = car_values

        with open(processed_dir / "car_congestion_cache.pkl", "wb") as f:
            pickle.dump(car_cache, f)
        print(f"Car congestion cache: {len(car_cache)} entries")

    # Get-off rate
    getoff_path = data_dir / "getoff_rate_raw.json"
    if getoff_path.exists():
        with open(getoff_path, "r", encoding="utf-8") as f:
            getoff_data = json.load(f)

        getoff_cache = {}
        for entry in getoff_data:
            station = entry["station"]
            hour = entry["hour"]
            dow = entry["dow"]
            data = entry["data"]

            car_values = _extract_car_values(data, "getOffCarRate")
            if car_values:
                getoff_cache[(station, hour, dow)] = car_values

        with open(processed_dir / "getoff_rate_cache.pkl", "wb") as f:
            pickle.dump(getoff_cache, f)
        print(f"Get-off rate cache: {len(getoff_cache)} entries")

    # Train congestion
    train_path = data_dir / "train_congestion_raw.json"
    if train_path.exists():
        with open(train_path, "r", encoding="utf-8") as f:
            train_data = json.load(f)

        train_cache = {}
        for entry in train_data:
            station = entry["station"]
            hour = entry["hour"]
            dow = entry["dow"]
            data = entry["data"]

            train_val = _extract_train_value(data)
            if train_val is not None:
                train_cache[(station, hour, dow)] = train_val

        with open(processed_dir / "train_congestion_cache.pkl", "wb") as f:
            pickle.dump(train_cache, f)
        print(f"Train congestion cache: {len(train_cache)} entries")


def _extract_car_values(data, key_hint="congestionCar"):
    """
    Extract array of 10 car values from API response.

    The SK API response structure may vary. Common formats:
    - {"contents": {"stat": [{"data": {"congestionCar": "30|35|..."}}, ...]}}
    - {"data": {"congestionCar": [30, 35, ...]}}
    - {"result": {"congestionCar": "30|35|40|..."}}
    """
    if not data:
        return None

    # Try direct access
    if isinstance(data, dict):
        # Nested: contents.stat[].data
        if "contents" in data:
            contents = data["contents"]
            if "stat" in contents:
                stats = contents["stat"]
                if isinstance(stats, list):
                    all_values = []
                    for stat in stats:
                        if "data" in stat:
                            val = stat["data"].get(key_hint)
                            if val:
                                if isinstance(val, str):
                                    parts = [float(x) for x in val.split("|") if x]
                                    all_values.append(parts)
                                elif isinstance(val, list):
                                    all_values.append([float(x) for x in val])
                    # Average across time intervals within the hour
                    if all_values:
                        arr = np.array(all_values)
                        return arr.mean(axis=0).tolist()

        # Direct data access
        for possible_key in [key_hint, "data", "result"]:
            if possible_key in data:
                val = data[possible_key]
                if isinstance(val, str) and "|" in val:
                    return [float(x) for x in val.split("|") if x]
                elif isinstance(val, list):
                    return [float(x) for x in val]
                elif isinstance(val, dict):
                    inner = val.get(key_hint)
                    if inner:
                        if isinstance(inner, str) and "|" in inner:
                            return [float(x) for x in inner.split("|") if x]
                        elif isinstance(inner, list):
                            return [float(x) for x in inner]

    return None


def _extract_train_value(data):
    """Extract single train congestion value from API response."""
    if not data:
        return None

    if isinstance(data, dict):
        if "contents" in data:
            contents = data["contents"]
            if "stat" in contents:
                stats = contents["stat"]
                if isinstance(stats, list):
                    values = []
                    for stat in stats:
                        if "data" in stat:
                            val = stat["data"].get("congestionTrain")
                            if val is not None:
                                values.append(float(val))
                    if values:
                        return np.mean(values)

        for key in ["congestionTrain", "data", "result"]:
            if key in data:
                val = data[key]
                if isinstance(val, (int, float)):
                    return float(val)
                elif isinstance(val, dict):
                    inner = val.get("congestionTrain")
                    if inner is not None:
                        return float(inner)

    return None


def collect_sample(station_name="강남", dow="MON"):
    """Collect sample data for one station to verify API response format."""
    code = LINE2_STATIONS.get(station_name)
    if not code:
        print(f"Station '{station_name}' not found in mapping")
        return

    print(f"\n=== Sample collection: {station_name} ({code}) {dow} ===")

    output_dir = PROJECT_ROOT / "data_raw" / "sk_api"
    output_dir.mkdir(parents=True, exist_ok=True)

    sample_data = {"station": station_name, "code": code, "dow": dow, "results": {}}

    for hour in [7, 8, 9, 12, 18, 19]:
        hh = str(hour).zfill(2)
        print(f"\n  Hour {hh}:")

        car = fetch_car_congestion(code, dow, hh)
        getoff = fetch_getoff_car_rate(code, dow, hh)
        train = fetch_train_congestion(code, dow, hh)

        sample_data["results"][hour] = {
            "car_congestion": car,
            "getoff_rate": getoff,
            "train_congestion": train,
        }

        if car:
            print(f"    car_congestion: {json.dumps(car, default=str)[:200]}")
        else:
            print(f"    car_congestion: None")
        if getoff:
            print(f"    getoff_rate: {json.dumps(getoff, default=str)[:200]}")
        else:
            print(f"    getoff_rate: None")
        if train:
            print(f"    train_congestion: {json.dumps(train, default=str)[:200]}")
        else:
            print(f"    train_congestion: None")

        time.sleep(0.5)

    # Save sample
    sample_path = output_dir / f"sample_{station_name}_{dow}.json"
    with open(sample_path, "w", encoding="utf-8") as f:
        json.dump(sample_data, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nSample saved: {sample_path}")

    return sample_data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SK Open API Data Collector")
    parser.add_argument("--test", action="store_true",
                       help="Test API connection only")
    parser.add_argument("--sample", type=str, default=None,
                       help="Collect sample for one station (e.g., '강남')")
    parser.add_argument("--full", action="store_true",
                       help="Collect full data for all stations")
    parser.add_argument("--process", action="store_true",
                       help="Process existing raw data into caches")
    parser.add_argument("--delay", type=float, default=0.3,
                       help="Delay between API calls (seconds)")
    args = parser.parse_args()

    if args.test:
        test_api_connection()
    elif args.sample:
        collect_sample(args.sample)
    elif args.full:
        collect_all_data(delay=args.delay)
    elif args.process:
        process_sk_data(PROJECT_ROOT / "data_raw" / "sk_api")
    else:
        # Default: test then sample
        print("Usage: python collect_sk_api.py [--test|--sample STATION|--full|--process]")
        print("\nRunning test + sample for 강남...")
        test_api_connection()
        collect_sample("강남")
