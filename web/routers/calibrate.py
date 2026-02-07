# -*- coding: utf-8 -*-
from fastapi import APIRouter
from web.schemas import (
    CalibrationRequest,
    CalibrationResponse,
    SensitivityPoint,
)
from web.dependencies import registry
from typing import List

router = APIRouter()


@router.post("/calibrate", response_model=CalibrationResponse)
async def calibrate(req: CalibrationRequest):
    """하이퍼파라미터를 런타임에 조정한다."""
    engine = registry.get_engine()

    if req.beta is not None:
        engine.BETA = req.beta
    if req.gamma is not None:
        engine.GAMMA = req.gamma

    weights_changed = False
    if req.escalator_weight is not None:
        engine.FACILITY_WEIGHTS["에스컬레이터"] = req.escalator_weight
        weights_changed = True
    if req.elevator_weight is not None:
        engine.FACILITY_WEIGHTS["엘리베이터"] = req.elevator_weight
        weights_changed = True
    if req.stairs_weight is not None:
        engine.FACILITY_WEIGHTS["계단"] = req.stairs_weight
        weights_changed = True

    if weights_changed:
        engine._build_facility_cache()

    if req.alpha_morning_rush is not None:
        engine.ALPHA_MAP["morning_rush"] = req.alpha_morning_rush
    if req.alpha_evening_rush is not None:
        engine.ALPHA_MAP["evening_rush"] = req.alpha_evening_rush
    if req.alpha_midday is not None:
        engine.ALPHA_MAP["midday"] = req.alpha_midday
    if req.alpha_evening is not None:
        engine.ALPHA_MAP["evening"] = req.alpha_evening
    if req.alpha_night is not None:
        engine.ALPHA_MAP["night"] = req.alpha_night
    if req.alpha_early is not None:
        engine.ALPHA_MAP["early"] = req.alpha_early

    return CalibrationResponse(
        beta=engine.BETA,
        gamma=engine.GAMMA,
        facility_weights=dict(engine.FACILITY_WEIGHTS),
        alpha_map=dict(engine.ALPHA_MAP),
    )


@router.get("/calibrate")
async def get_calibration():
    """현재 하이퍼파라미터 값을 반환한다."""
    engine = registry.get_engine()
    return CalibrationResponse(
        beta=engine.BETA,
        gamma=engine.GAMMA,
        facility_weights=dict(engine.FACILITY_WEIGHTS),
        alpha_map=dict(engine.ALPHA_MAP),
    )


@router.get("/sensitivity", response_model=List[SensitivityPoint])
async def sensitivity_analysis(
    boarding: str = "강남",
    destination: str = "시청",
    hour: int = 8,
):
    """β를 0.0~1.0까지 sweep하여 각 칸의 점수 변화를 반환한다."""
    engine = registry.get_engine()
    original_beta = engine.BETA
    direction = registry.auto_direction(boarding, destination)

    results = []
    for beta_100 in range(0, 105, 5):  # 0.00 ~ 1.00, step 0.05
        beta = beta_100 / 100.0
        engine.BETA = beta
        scores_df = engine.compute_seatscore(
            boarding, destination, hour, direction
        )
        for _, row in scores_df.iterrows():
            results.append(SensitivityPoint(
                beta=beta,
                car=int(row["car"]),
                score=round(float(row["score"]), 1),
            ))

    engine.BETA = original_beta
    return results
