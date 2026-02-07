# -*- coding: utf-8 -*-
from fastapi import APIRouter
from web.dependencies import registry

router = APIRouter()


@router.get("/stations")
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
