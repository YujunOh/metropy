# -*- coding: utf-8 -*-
import os
from dataclasses import replace
from fastapi import APIRouter, HTTPException, Header, Depends
from api.schemas import (
    CalibrationRequest,
    CalibrationResponse,
    SensitivityPoint,
    SensitivityPointGamma,
    SensitivityPointDelta,
)
from api.dependencies import registry
from api.cache import invalidate_recommend_cache
from typing import List, Optional

router = APIRouter()


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """API Key 검증 (env var METROPY_API_KEY가 설정된 경우만)"""
    api_key = os.getenv("METROPY_API_KEY")
    if api_key:  # env var가 설정된 경우만 검증
        if not x_api_key or x_api_key != api_key:
            raise HTTPException(status_code=403, detail="유효하지 않은 API 키입니다")


@router.post(
    "/calibrate",
    response_model=CalibrationResponse,
    summary="하이퍼파라미터 조정",
    description="SeatScore 엔진의 하이퍼파라미터(β, γ, δ, 시설 가중치, 시간대 배율)를 "
    "런타임에 조정합니다. 변경 시 추천 캠시가 자동 무효화됩니다.",
    response_description="적용된 파라미터 값",
)
async def calibrate(req: CalibrationRequest, _: None = Depends(verify_api_key)):
    """하이퍼파라미터를 런타임에 조정한다."""
    engine = registry.get_engine()

    with registry.engine_lock:
        current_params = engine.params
        beta = req.beta if req.beta is not None else current_params.beta
        gamma = req.gamma if req.gamma is not None else current_params.gamma
        delta = req.delta if req.delta is not None else current_params.delta

        facility_weights = dict(current_params.facility_weights)
        alpha_map = dict(current_params.alpha_map)

        weights_changed = False
        if req.escalator_weight is not None:
            facility_weights["에스컬레이터"] = req.escalator_weight
            weights_changed = True
        if req.elevator_weight is not None:
            facility_weights["엘리베이터"] = req.elevator_weight
            weights_changed = True
        if req.stairs_weight is not None:
            facility_weights["계단"] = req.stairs_weight
            weights_changed = True

        if req.alpha_morning_rush is not None:
            alpha_map["morning_rush"] = req.alpha_morning_rush
        if req.alpha_evening_rush is not None:
            alpha_map["evening_rush"] = req.alpha_evening_rush
        if req.alpha_midday is not None:
            alpha_map["midday"] = req.alpha_midday
        if req.alpha_evening is not None:
            alpha_map["evening"] = req.alpha_evening
        if req.alpha_night is not None:
            alpha_map["night"] = req.alpha_night
        if req.alpha_early is not None:
            alpha_map["early"] = req.alpha_early

        new_params = replace(
            current_params,
            beta=beta,
            gamma=gamma,
            delta=delta,
            facility_weights=facility_weights,
            alpha_map=alpha_map,
        )
        engine.params = new_params

        if weights_changed:
            engine._build_facility_cache()

        params = engine.params

    # calibrate 변경 시 recommend 캐시 무효화
    invalidate_recommend_cache()

    return CalibrationResponse(
        beta=params.beta,
        gamma=params.gamma,
        delta=params.delta,
        facility_weights=dict(params.facility_weights),
        alpha_map=dict(params.alpha_map),
    )


@router.get(
    "/calibrate",
    response_model=CalibrationResponse,
    summary="현재 파라미터 조회",
    description="현재 설정된 SeatScore 하이퍼파라미터(β, γ, δ, 시설 가중치, 시간대 배율)를 반환합니다.",
    response_description="현재 설정된 파라미터 값",
)
async def get_calibration():
    """현재 하이퍼파라미터 값을 반환한다."""
    engine = registry.get_engine()
    params = engine.params
    return CalibrationResponse(
        beta=params.beta,
        gamma=params.gamma,
        delta=params.delta,
        facility_weights=dict(params.facility_weights),
        alpha_map=dict(params.alpha_map),
    )


@router.get(
    "/sensitivity",
    response_model=List[SensitivityPoint],
    summary="β 민감도 분석",
    description="혼잡 회피 강도(β)를 0.0~1.0까지 0.05 간격으로 sweep하며, "
    "각 칸의 SeatScore 점수 변화를 반환합니다. 파라미터 튜닝에 활용할 수 있습니다.",
    response_description="β값별 칸별 점수 배열",
)
async def sensitivity_analysis(
    boarding: str = "강남",
    destination: str = "시청",
    hour: int = 8,
):
    """β를 0.0~1.0까지 sweep하여 각 칸의 점수 변화를 반환한다."""
    engine = registry.get_engine()
    direction = registry.auto_direction(boarding, destination)

    results = []
    with registry.engine_lock:
        original_params = engine.params
        try:
            for beta_100 in range(0, 105, 5):  # 0.00 ~ 1.00, step 0.05
                beta = beta_100 / 100.0
                engine.params = replace(original_params, beta=beta)
                scores_df = engine.compute_seatscore(
                    boarding, destination, hour, direction
                )
                for _, row in scores_df.iterrows():
                    results.append(SensitivityPoint(
                        beta=beta,
                        car=int(row["car"]),
                        score=round(float(row["score"]), 1),
                    ))
        finally:
            engine.params = original_params
    return results


@router.get(
    "/sensitivity/gamma",
    response_model=List[SensitivityPointGamma],
    summary="γ 민감도 분석",
    description="하차 분포 압축 강도(γ)를 0.1~1.0까지 sweep하며, "
    "경쟁계수 압축이 추천 결과에 미치는 영향을 분석합니다.",
    response_description="γ값별 칸별 점수 배열",
)
async def sensitivity_gamma(
    boarding: str = "강남",
    destination: str = "시청",
    hour: int = 8,
):
    """γ(GAMMA)를 0.1~1.0까지 sweep하여 경쟁계수 압축 효과를 분석한다."""
    engine = registry.get_engine()
    direction = registry.auto_direction(boarding, destination)

    results = []
    with registry.engine_lock:
        original_params = engine.params
        try:
            for gamma_10 in range(1, 11):  # 0.1 ~ 1.0, step 0.1
                gamma = gamma_10 / 10.0
                engine.params = replace(original_params, gamma=gamma)
                scores_df = engine.compute_seatscore(
                    boarding, destination, hour, direction
                )
                for _, row in scores_df.iterrows():
                    results.append(SensitivityPointGamma(
                        gamma=gamma,
                        car=int(row["car"]),
                        score=round(float(row["score"]), 1),
                    ))
        finally:
            engine.params = original_params
    return results


@router.get(
    "/sensitivity/delta",
    response_model=List[SensitivityPointDelta],
    summary="δ 민감도 분석",
    description="초기 착석 보너스 강도(δ)를 0.0~0.5까지 sweep하며, "
    "탑승 즉시 착석 가능성이 추천 결과에 미치는 영향을 분석합니다.",
    response_description="δ값별 칸별 점수 배열",
)
async def sensitivity_delta(
    boarding: str = "강남",
    destination: str = "시청",
    hour: int = 8,
):
    """δ(DELTA)를 0.0~0.5까지 sweep하여 초기 착석 보너스 효과를 분석한다."""
    engine = registry.get_engine()
    direction = registry.auto_direction(boarding, destination)

    results = []
    with registry.engine_lock:
        original_params = engine.params
        try:
            for delta_100 in range(0, 55, 5):  # 0.00 ~ 0.50, step 0.05
                delta = delta_100 / 100.0
                engine.params = replace(original_params, delta=delta)
                scores_df = engine.compute_seatscore(
                    boarding, destination, hour, direction
                )
                for _, row in scores_df.iterrows():
                    results.append(SensitivityPointDelta(
                        delta=delta,
                        car=int(row["car"]),
                        score=round(float(row["score"]), 1),
                    ))
        finally:
            engine.params = original_params
    return results
