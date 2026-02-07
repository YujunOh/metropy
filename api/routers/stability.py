"""
Rank Stability Analysis Router
===============================
Perturbs model parameters and checks how often the "best car" ranking changes.
A stable model should maintain consistent rankings under reasonable perturbations.
"""
import random
from dataclasses import replace
from typing import List
from fastapi import APIRouter
from api.schemas import RankStabilityResponse, RankStabilityCarResult
from api.dependencies import registry

router = APIRouter()


@router.get(
    "/stability",
    response_model=RankStabilityResponse,
    summary="추천 순위 안정성 분석",
    description="α 파라미터를 ±20% 범위로 N회 교란하여 최적 칸 추천이 "
    "얼마나 일관되게 유지되는지 검증합니다. 칸별 순위 변동 통계 포함.",
    response_description="기준 순위, 변동 횟수, 점수 평균/표준편차 등",
)
async def rank_stability(
    boarding: str = "강남",
    destination: str = "시청",
    hour: int = 8,
    n_perturbations: int = 50,
):
    """
    Rank stability analysis: perturb alpha by ±20% across N trials
    and report how often the best-car recommendation changes.

    A "stable" recommendation means the best car survives most perturbations.
    """
    engine = registry.get_engine()
    direction = registry.auto_direction(boarding, destination)

    with registry.engine_lock:
        # Baseline
        base_df = engine.compute_seatscore(boarding, destination, hour, direction)
        base_ranks = {int(row["car"]): int(row["rank"]) for _, row in base_df.iterrows()}
        base_scores = {int(row["car"]): float(row["score"]) for _, row in base_df.iterrows()}
        base_best = int(base_df.iloc[0]["car"])

        # Collect perturbed results
        rng = random.Random(42)
        all_ranks = {c: [] for c in range(1, 11)}
        all_scores = {c: [] for c in range(1, 11)}
        best_car_changes = 0

        for _ in range(n_perturbations):
            # Perturb alpha by ±20%
            factor = 1.0 + rng.uniform(-0.2, 0.2)
            # Atomic params swap: scale alpha_map values instead of monkey-patching _get_alpha
            original_params = engine.params
            perturbed_alpha_map = {
                k: round(v * factor, 4)
                for k, v in original_params.alpha_map.items()
            }
            engine.params = replace(original_params, alpha_map=perturbed_alpha_map)

            try:
                df = engine.compute_seatscore(boarding, destination, hour, direction)
                trial_best = int(df.iloc[0]["car"])
                if trial_best != base_best:
                    best_car_changes += 1
                for _, row in df.iterrows():
                    c = int(row["car"])
                    all_ranks[c].append(int(row["rank"]))
                    all_scores[c].append(float(row["score"]))
            finally:
                engine.params = original_params

    # Build response
    cars: List[RankStabilityCarResult] = []
    for c in range(1, 11):
        ranks = all_ranks[c]
        scores = all_scores[c]
        rank_set = set(ranks)
        rank_changes = len(rank_set) - 1  # unique ranks - 1

        avg_s = sum(scores) / len(scores) if scores else 0.0
        std_s = (
            (sum((s - avg_s) ** 2 for s in scores) / len(scores)) ** 0.5
            if scores else 0.0
        )

        cars.append(RankStabilityCarResult(
            car=c,
            base_rank=base_ranks[c],
            base_score=round(base_scores[c], 1),
            rank_changes=rank_changes,
            min_rank=min(ranks) if ranks else base_ranks[c],
            max_rank=max(ranks) if ranks else base_ranks[c],
            avg_score=round(avg_s, 1),
            score_std=round(std_s, 2),
        ))

    cars.sort(key=lambda x: x.base_rank)

    return RankStabilityResponse(
        boarding=boarding,
        destination=destination,
        hour=hour,
        direction=direction,
        n_perturbations=n_perturbations,
        best_car_stable=(best_car_changes == 0),
        best_car_change_pct=round(best_car_changes / n_perturbations * 100, 1),
        cars=cars,
    )
