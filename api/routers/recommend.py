import asyncio
import logging

from fastapi import APIRouter, HTTPException
from api.schemas import (
    RecommendRequest, RecommendResponse, CarScore, StationContribution,
)
from api.dependencies import registry
from api.cache import recommend_cache

router = APIRouter()


@router.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="최적 탑승 칸 추천",
    description="출발역, 도착역, 탑승 시간을 기반으로 SeatScore v4 엔진이 10량 열차의 "
    "칸별 착석 효용 점수를 계산하고, 최적 탑승 칸을 추천합니다. "
    "경유역 하차 패턴, 혼잡도, 시설 위치 등 10가지 공공데이터를 종합 분석합니다.",
    response_description="칸별 점수, 최적/최악 칸, 경유역 기여도 등 상세 추천 결과",
)
async def recommend(req: RecommendRequest):
    engine = registry.get_engine()

    # 방향 자동 판별
    direction = req.direction
    if not direction:
        direction = registry.auto_direction(req.boarding, req.destination)

    # 입력 검증: 역 존재 여부 확인
    stations = engine.station_order
    if req.boarding not in stations:
        raise HTTPException(status_code=404, detail=f"출발역을 찾을 수 없습니다: {req.boarding}")
    if req.destination not in stations:
        raise HTTPException(status_code=404, detail=f"도착역을 찾을 수 없습니다: {req.destination}")

    # 입력 검증: 출발역 ≠ 도착역
    if req.boarding == req.destination:
        raise HTTPException(status_code=400, detail="출발역과 도착역이 같을 수 없습니다")

    # 입력 검증: hour 범위 (0-23)
    if not (0 <= req.hour <= 23):
        raise HTTPException(status_code=400, detail="시간은 0~23 범위여야 합니다")

    # 캐시 조회
    cached_result = recommend_cache.get(req.boarding, req.destination, req.hour, direction, req.dow)
    if cached_result is not None:
        return cached_result

    try:
        result = await asyncio.to_thread(
            engine.recommend, req.boarding, req.destination, req.hour, direction, req.dow
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.error(f"Recommend failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="추천 계산 중 오류가 발생했습니다")

    scores_df = result["scores"]
    seat_times = result.get("seat_times", {})
    p_seated_dict = result.get("p_seated", {})
    car_scores = [
        CarScore(
            car=int(row["car"]),
            score=round(float(row["score"]), 1),
            rank=int(row["rank"]),
            benefit=round(float(row["benefit"]), 2),
            penalty=round(float(row["penalty"]), 2),
            load_factor=round(float(row["load_factor"]), 4),
            estimated_seat_minutes=seat_times.get(int(row["car"])),
            p_seated=p_seated_dict.get(int(row["car"])),
        )
        for _, row in scores_df.iterrows()
    ]

    # Per-station contributions for best car (for explanation UI)
    station_contribs = result.get("station_contributions", {})
    contribs_serialized = None
    if station_contribs:
        contribs_serialized = {}
        for car_num, contribs in station_contribs.items():
            contribs_serialized[str(car_num)] = [
                StationContribution(
                    station=c.get("station"),
                    D=c.get("D", 0.0),
                    T=c.get("T", 0.0),
                    w=c.get("w", 0.0),
                    L=c.get("L", 1.0),
                    L_eff=c.get("L_eff", 1.0),
                    contribution=c.get("contribution", 0.0),
                    p_seated=c.get("p_seated"),
                    p_sit=c.get("p_sit", 1.0),
                    A=c.get("A", 0.0),
                    C=c.get("C", 0.0),
                    C_adj=c.get("C_adj", 0.0),
                    p_capture=c.get("p_capture", 0.0),
                    p_first=c.get("p_first", 0.0),
                ) for c in contribs
            ]

    # Serialize load factors with string keys for JSON
    load_factors_raw = result.get("load_factors", {})
    load_factors_serialized = {
        str(k): round(v, 4) for k, v in load_factors_raw.items()
    } if load_factors_raw else None

    response = RecommendResponse(
        boarding=result["boarding"],
        destination=result["destination"],
        hour=result["hour"],
        direction=direction,
        dow=req.dow,
        alpha=result["alpha"],
        weather_factor=result.get("weather_factor"),
        best_car=result["best_car"],
        best_score=round(float(result["best_score"]), 1),
        worst_car=result["worst_car"],
        worst_score=round(float(result["worst_score"]), 1),
        score_spread=round(float(result["score_spread"]), 1),
        n_intermediate=result["n_intermediate"],
        intermediates=result["intermediates"],
        car_scores=car_scores,
        boarding_congestion=round(result["boarding_congestion"], 1) if result.get("boarding_congestion") else None,
        load_factors=load_factors_serialized,
        data_sources=result.get("data_sources", []),
        data_quality=result.get("data_quality"),
        station_contributions=contribs_serialized,
        best_seat_time=seat_times.get(result["best_car"]),
        p_seated_best=p_seated_dict.get(result["best_car"]),
    )
    
    # 캐시에 저장
    recommend_cache.set(req.boarding, req.destination, req.hour, direction, req.dow, response)
    
    return response
