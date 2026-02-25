# -*- coding: utf-8 -*-
import math
from fastapi import APIRouter, Query
from api.dependencies import registry
from api.schemas import NearestStationItem, NearestStationResponse

router = APIRouter()

# 2호선 역 좌표 및 코드 (순환선 순서)
LINE2_STATION_DATA = [
    ("시청", "201", 37.5662, 126.9779),
    ("을지로입구", "202", 37.5658, 126.9822),
    ("을지로3가", "203", 37.5662, 126.9914),
    ("을지로4가", "204", 37.5669, 127.0017),
    ("동대문역사문화공원", "205", 37.5652, 127.0079),
    ("신당", "206", 37.5661, 127.0177),
    ("상왕십리", "207", 37.5658, 127.0294),
    ("왕십리", "208", 37.5617, 127.0377),
    ("한양대", "209", 37.5559, 127.0442),
    ("뚝섬", "210", 37.5467, 127.0472),
    ("성수", "211", 37.5445, 127.0557),
    ("건대입구", "212", 37.5401, 127.0695),
    ("구의", "213", 37.5371, 127.0855),
    ("강변", "214", 37.5348, 127.0944),
    ("잠실나루", "215", 37.5202, 127.1020),
    ("잠실", "216", 37.5133, 127.1000),
    ("잠실새내", "217", 37.5112, 127.0860),
    ("종합운동장", "218", 37.5107, 127.0735),
    ("삼성", "219", 37.5088, 127.0633),
    ("선릉", "220", 37.5045, 127.0493),
    ("역삼", "221", 37.5004, 127.0364),
    ("강남", "222", 37.4979, 127.0276),
    ("교대", "223", 37.4934, 127.0145),
    ("서초", "224", 37.4916, 127.0078),
    ("방배", "225", 37.4814, 126.9976),
    ("사당", "226", 37.4766, 126.9816),
    ("낙성대", "227", 37.4768, 126.9636),
    ("서울대입구", "228", 37.4814, 126.9527),
    ("봉천", "229", 37.4821, 126.9426),
    ("신림", "230", 37.4842, 126.9296),
    ("신대방", "231", 37.4872, 126.9130),
    ("구로디지털단지", "232", 37.4851, 126.9015),
    ("대림", "233", 37.4932, 126.8956),
    ("신도림", "234", 37.5089, 126.8913),
    ("문래", "235", 37.5178, 126.8950),
    ("영등포구청", "236", 37.5244, 126.8960),
    ("당산", "237", 37.5345, 126.9025),
    ("합정", "238", 37.5494, 126.9139),
    ("홍대입구", "239", 37.5571, 126.9245),
    ("신촌", "240", 37.5559, 126.9368),
    ("이대", "241", 37.5566, 126.9458),
    ("아현", "242", 37.5573, 126.9567),
    ("충정로", "243", 37.5598, 126.9637),
]

EARTH_RADIUS_M = 6_371_000  # Earth radius in meters


# 하버사인 공식 (stackoverflow에서 가져옴)
def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in meters between two coordinates using Haversine formula."""
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


@router.get(
    "/stations",
    summary="2호선 역 목록 조회",
    description="서울 지하철 2호선 본선(순환) 43개역의 목록을 반환합니다. "
    "정규화된 역명과 원본 표시명을 함께 제공합니다.",
    response_description="역 목록 (name: 정규화명, name_display: 표시명)",
)
async def get_stations():
    """2호선 역 목록을 반환한다. 본선(순환) 44개역만."""
    engine = registry.get_engine()
    # 본선: index 0~43 (시청~충정로), index 44는 시청 중복
    main_stations = engine.station_order[:44]

    # 원본 역명도 함께 제공 (distance_df에서)
    df = engine.distance_df
    result = []
    seen = set()
    for s in main_stations:
        if s in seen:
            continue
        seen.add(s)
        row = df[df["station_normalized"] == s]
        display = row.iloc[0]["역명"] if len(row) > 0 else s
        result.append({"name": s, "name_display": str(display)})
    return result


@router.get(
    "/nearest-station",
    response_model=NearestStationResponse,
    summary="GPS 기반 최근접 역 조회",
    description="주어진 위도/경도 좌표에서 가장 가까운 2호선 역 3개를 "
    "Haversine 공식으로 계산하여 반환합니다. 거리(m) 포함.",
    response_description="최근접 3개역 (이름, 코드, 거리, 좌표)",
)
async def get_nearest_station(
    lat: float = Query(..., description="위도 (예: 37.4979)"),
    lng: float = Query(..., description="경도 (예: 127.0276)"),
):
    """Return the nearest 3 Line 2 stations to the given coordinates."""
    distances = []
    for name, code, s_lat, s_lng in LINE2_STATION_DATA:
        dist = _haversine(lat, lng, s_lat, s_lng)
        distances.append((name, code, dist, s_lat, s_lng))

    distances.sort(key=lambda x: x[2])
    nearest_3 = distances[:3]

    return NearestStationResponse(
        stations=[
            NearestStationItem(
                name=name,
                code=code,
                distance_m=round(dist, 1),
                lat=s_lat,
                lng=s_lng,
            )
            for name, code, dist, s_lat, s_lng in nearest_3
        ]
    )
