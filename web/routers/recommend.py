# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException
from web.schemas import (
    RecommendRequest, RecommendResponse, CarScore, StationContribution,
)
from web.dependencies import registry

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    engine = registry.get_engine()

    # 방향 자동 판별
    direction = req.direction
    if not direction:
        direction = registry.auto_direction(req.boarding, req.destination)

    try:
        result = engine.recommend(req.boarding, req.destination, req.hour, direction, req.dow)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    scores_df = result["scores"]
    car_scores = [
        CarScore(
            car=int(row["car"]),
            score=round(float(row["score"]), 1),
            rank=int(row["rank"]),
            benefit=round(float(row["benefit"]), 2),
            penalty=round(float(row["penalty"]), 2),
            load_factor=round(float(row["load_factor"]), 4),
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
                StationContribution(**c) for c in contribs
            ]

    # Serialize load factors with string keys for JSON
    load_factors_raw = result.get("load_factors", {})
    load_factors_serialized = {
        str(k): round(v, 4) for k, v in load_factors_raw.items()
    } if load_factors_raw else None

    return RecommendResponse(
        boarding=result["boarding"],
        destination=result["destination"],
        hour=result["hour"],
        direction=direction,
        dow=req.dow,
        alpha=result["alpha"],
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
        station_contributions=contribs_serialized,
    )
