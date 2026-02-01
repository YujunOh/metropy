"""
TMAP Transit API - 2호선 역간 실제 이동시간 수집
================================================
TMAP 대중교통 API를 사용해 연속 역간 실제 이동시간을 수집하고
SeatScore의 T(s→dest) 계산을 거리 기반에서 시간 기반으로 업그레이드.

비용: 0.88원/건 (Premium), 43 역 = ~38원
"""

import json
import time
import pickle
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent

SK_API_KEY = "V4kZORPDLL4tosV1csaYr1lM98hEfT6B1TAjuRx7"
TRANSIT_URL = "https://apis.openapi.sk.com/transit/routes"
TRANSIT_SUMMARY_URL = "https://apis.openapi.sk.com/transit/routes/sub"

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "appKey": SK_API_KEY,
}

# 2호선 역 좌표 (순환선 순서, order 0~42)
LINE2_COORDS = [
    ("시청",           37.5662, 126.9779),
    ("을지로입구",     37.5658, 126.9822),
    ("을지로3가",      37.5662, 126.9914),
    ("을지로4가",      37.5669, 127.0017),
    ("동대문역사문화공원", 37.5652, 127.0079),
    ("신당",           37.5661, 127.0177),
    ("상왕십리",       37.5658, 127.0294),
    ("왕십리",         37.5617, 127.0377),
    ("한양대",         37.5559, 127.0442),
    ("뚝섬",           37.5467, 127.0472),
    ("성수",           37.5445, 127.0557),
    ("건대입구",       37.5401, 127.0695),
    ("구의",           37.5371, 127.0855),
    ("강변",           37.5348, 127.0944),
    ("잠실나루",       37.5202, 127.1020),
    ("잠실",           37.5133, 127.1000),
    ("잠실새내",       37.5112, 127.0860),
    ("종합운동장",     37.5107, 127.0735),
    ("삼성",           37.5088, 127.0633),
    ("선릉",           37.5045, 127.0493),
    ("역삼",           37.5004, 127.0364),
    ("강남",           37.4979, 127.0276),
    ("교대",           37.4934, 127.0145),
    ("서초",           37.4916, 127.0078),
    ("방배",           37.4814, 126.9976),
    ("사당",           37.4766, 126.9816),
    ("낙성대",         37.4768, 126.9636),
    ("서울대입구",     37.4814, 126.9527),
    ("봉천",           37.4821, 126.9426),
    ("신림",           37.4842, 126.9296),
    ("신대방",         37.4872, 126.9130),
    ("구로디지털단지", 37.4851, 126.9015),
    ("대림",           37.4932, 126.8956),
    ("신도림",         37.5089, 126.8913),
    ("문래",           37.5178, 126.8950),
    ("영등포구청",     37.5244, 126.8960),
    ("당산",           37.5345, 126.9025),
    ("합정",           37.5494, 126.9139),
    ("홍대입구",       37.5571, 126.9245),
    ("신촌",           37.5559, 126.9368),
    ("이대",           37.5566, 126.9458),
    ("아현",           37.5573, 126.9567),
    ("충정로",         37.5598, 126.9637),
]


def fetch_transit_time(start_lat, start_lng, end_lat, end_lng):
    """
    TMAP 대중교통 요약 API 호출.
    Returns: (subway_time_sec, total_time_sec, distance_m) or None
    """
    body = {
        "startX": str(start_lng),
        "startY": str(start_lat),
        "endX": str(end_lng),
        "endY": str(end_lat),
        "count": 5,
        "format": "json",
    }

    try:
        resp = requests.post(TRANSIT_SUMMARY_URL, headers=HEADERS, json=body, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()
        itineraries = data.get("metaData", {}).get("plan", {}).get("itineraries", [])

        # 지하철 경로 찾기 (pathType=1)
        for itin in itineraries:
            if itin.get("pathType") == 1:  # subway only
                return {
                    "total_time": itin["totalTime"],
                    "walk_time": itin.get("totalWalkTime", 0),
                    "transit_time": itin["totalTime"] - itin.get("totalWalkTime", 0),
                    "distance": itin.get("totalDistance", 0),
                    "transfers": itin.get("transferCount", 0),
                    "fare": itin.get("fare", {}).get("regular", {}).get("totalFare", 0),
                }

        # 지하철 전용이 없으면 가장 짧은 결과 사용
        if itineraries:
            best = min(itineraries, key=lambda x: x["totalTime"])
            return {
                "total_time": best["totalTime"],
                "walk_time": best.get("totalWalkTime", 0),
                "transit_time": best["totalTime"] - best.get("totalWalkTime", 0),
                "distance": best.get("totalDistance", 0),
                "transfers": best.get("transferCount", 0),
                "fare": best.get("fare", {}).get("regular", {}).get("totalFare", 0),
                "pathType": best.get("pathType"),
            }

        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None


def collect_segment_times():
    """
    연속 역간 이동시간 수집 (43개 구간).

    시청→을지로입구, 을지로입구→을지로3가, ..., 충정로→시청
    """
    n = len(LINE2_COORDS)
    segments = []

    print(f"\n{'='*60}")
    print(f"  TMAP Transit API - 2호선 역간 이동시간 수집")
    print(f"{'='*60}")
    print(f"  구간 수: {n} (순환)")
    print(f"  예상 비용: {n * 0.88:.0f}원 (0.88원/건)")
    print(f"{'='*60}\n")

    for i in range(n):
        j = (i + 1) % n
        name_a, lat_a, lng_a = LINE2_COORDS[i]
        name_b, lat_b, lng_b = LINE2_COORDS[j]

        result = fetch_transit_time(lat_a, lng_a, lat_b, lng_b)

        if result:
            transit_sec = result["transit_time"]
            total_sec = result["total_time"]
            dist_m = result["distance"]
            print(f"  [{i+1:2d}/{n}] {name_a:10s} -> {name_b:10s}: "
                  f"{transit_sec:4d}s ({transit_sec/60:.1f}min) "
                  f"| total {total_sec}s | {dist_m}m")
            segments.append({
                "from": name_a,
                "to": name_b,
                "from_idx": i,
                "to_idx": j,
                "transit_time_sec": transit_sec,
                "total_time_sec": total_sec,
                "walk_time_sec": result.get("walk_time", 0),
                "distance_m": dist_m,
                "transfers": result.get("transfers", 0),
                "fare": result.get("fare", 0),
            })
        else:
            print(f"  [{i+1:2d}/{n}] {name_a:10s} -> {name_b:10s}: FAILED")
            # 실패 시 기본값 (평균 120초)
            segments.append({
                "from": name_a,
                "to": name_b,
                "from_idx": i,
                "to_idx": j,
                "transit_time_sec": 120,
                "total_time_sec": 120,
                "walk_time_sec": 0,
                "distance_m": 0,
                "transfers": 0,
                "fare": 0,
                "estimated": True,
            })

        time.sleep(0.5)

    return segments


def build_travel_time_matrix(segments):
    """
    구간별 이동시간을 전체 역간 누적 이동시간 매트릭스로 변환.

    결과: travel_times[from_station][to_station] = seconds (내선 방향)
    """
    n = len(LINE2_COORDS)
    station_names = [s[0] for s in LINE2_COORDS]

    # 누적 시간 (내선 방향: 시청→을지로입구→...→충정로→시청)
    cumulative = [0]
    for seg in segments:
        cumulative.append(cumulative[-1] + seg["transit_time_sec"])

    # 매트릭스 생성
    matrix = {}
    for i in range(n):
        matrix[station_names[i]] = {}
        for j in range(n):
            if i == j:
                matrix[station_names[i]][station_names[j]] = 0
            else:
                # 내선 (시계방향): i → j
                inner = (cumulative[j] - cumulative[i]) % cumulative[-1]
                # 외선 (반시계방향): j → i
                outer = cumulative[-1] - inner
                matrix[station_names[i]][station_names[j]] = min(inner, outer)

    return matrix, cumulative


def save_results(segments, matrix, cumulative):
    """수집 결과 저장."""
    out_dir = PROJECT_ROOT / "data_processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_dir = PROJECT_ROOT / "data_raw" / "transit"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Raw segments
    with open(raw_dir / "segment_times.json", "w", encoding="utf-8") as f:
        json.dump(segments, f, ensure_ascii=False, indent=2)

    # Travel time matrix (pickle)
    with open(out_dir / "travel_time_matrix.pkl", "wb") as f:
        pickle.dump(matrix, f)

    # Cumulative times (pickle)
    station_names = [s[0] for s in LINE2_COORDS]
    with open(out_dir / "cumulative_times.pkl", "wb") as f:
        pickle.dump({"stations": station_names, "cumulative": cumulative}, f)

    # Summary stats
    times = [s["transit_time_sec"] for s in segments]
    print(f"\n{'='*60}")
    print(f"  수집 완료")
    print(f"{'='*60}")
    print(f"  구간 수:       {len(segments)}")
    print(f"  총 순환시간:   {sum(times)}s ({sum(times)/60:.1f}min)")
    print(f"  평균 구간:     {sum(times)/len(times):.0f}s ({sum(times)/len(times)/60:.1f}min)")
    print(f"  최단 구간:     {min(times)}s ({min(times)/60:.1f}min)")
    print(f"  최장 구간:     {max(times)}s ({max(times)/60:.1f}min)")
    print(f"  저장 위치:")
    print(f"    - {raw_dir / 'segment_times.json'}")
    print(f"    - {out_dir / 'travel_time_matrix.pkl'}")
    print(f"    - {out_dir / 'cumulative_times.pkl'}")
    print(f"{'='*60}")


def collect_long_routes():
    """
    긴 구간 이동시간 수집 (검증용).
    시청→강남, 강남→시청, 홍대입구→잠실 등.
    """
    test_pairs = [
        ("시청", "강남", 0, 21),
        ("강남", "시청", 21, 0),
        ("홍대입구", "잠실", 38, 15),
        ("신도림", "왕십리", 33, 7),
    ]

    print("\n=== 검증용 장거리 이동시간 ===")
    for name_a, name_b, idx_a, idx_b in test_pairs:
        _, lat_a, lng_a = LINE2_COORDS[idx_a]
        _, lat_b, lng_b = LINE2_COORDS[idx_b]
        result = fetch_transit_time(lat_a, lng_a, lat_b, lng_b)
        if result:
            t = result["transit_time"]
            print(f"  {name_a:10s} -> {name_b:10s}: {t}s ({t/60:.1f}min)")
        else:
            print(f"  {name_a:10s} -> {name_b:10s}: FAILED")
        time.sleep(0.5)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="TMAP Transit 이동시간 수집")
    parser.add_argument("--collect", action="store_true", help="전체 수집")
    parser.add_argument("--verify", action="store_true", help="검증용 장거리 수집")
    parser.add_argument("--test", action="store_true", help="API 테스트 (1건)")
    args = parser.parse_args()

    if args.test:
        name_a, lat_a, lng_a = LINE2_COORDS[0]  # 시청
        name_b, lat_b, lng_b = LINE2_COORDS[1]  # 을지로입구
        r = fetch_transit_time(lat_a, lng_a, lat_b, lng_b)
        if r:
            print(f"[OK] {name_a} -> {name_b}: {r['transit_time']}s")
        else:
            print("[FAIL]")
    elif args.collect:
        segments = collect_segment_times()
        matrix, cumulative = build_travel_time_matrix(segments)
        save_results(segments, matrix, cumulative)
        collect_long_routes()  # 검증
    elif args.verify:
        collect_long_routes()
    else:
        parser.print_help()
