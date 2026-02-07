"""
Validation API Router
=====================
Computes accuracy metrics by comparing SeatScore recommendations
against user feedback data.
"""
import logging
import sqlite3
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from api.schemas import (
    ValidationRequest, ValidationResponse, ValidationMetrics,
    ValidationFeedbackItem,
)
from api.dependencies import registry

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data_processed" / "feedback.db"


def _load_feedback_from_db() -> List[dict]:
    """Load all feedback rows from SQLite database."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT boarding, alighting, hour, dow, recommended_car, "
            "actual_car, satisfaction, got_seat FROM feedback"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _compute_metrics(feedback: List[dict]) -> ValidationMetrics:
    """
    Compute validation metrics from feedback data.

    Metrics:
    - mean_satisfaction: average user satisfaction (1-5 scale)
    - seat_success_rate: fraction of users who got a seat
    - rank_correlation: Spearman correlation between seatscore rank and satisfaction
    - top1_accuracy: fraction where recommended car matched user preference
    - mean_score_satisfied/unsatisfied: avg seatscore for happy vs unhappy users
    """
    if not feedback:
        return ValidationMetrics(
            total_feedback=0,
            mean_satisfaction=0.0,
            seat_success_rate=0.0,
            rank_correlation=None,
            top1_accuracy=0.0,
            mean_score_satisfied=None,
            mean_score_unsatisfied=None,
        )

    engine = registry.get_engine()
    n = len(feedback)

    satisfactions = [f["satisfaction"] for f in feedback]
    mean_sat = sum(satisfactions) / n

    seat_hits = sum(1 for f in feedback if f.get("got_seat", False) or f.get("got_seat") == 1)
    seat_rate = seat_hits / n

    # Compute seatscore ranks for each feedback entry
    scores_for_rec_car = []
    ranks_for_rec_car = []
    satisfactions_for_corr = []  # 대응하는 만족도 (ranks_for_rec_car와 동일 인덱스)
    top1_hits = 0

    satisfied_scores = []  # satisfaction >= 4
    unsatisfied_scores = []  # satisfaction <= 2
    skipped = 0

    for f in feedback:
        try:
            direction = registry.auto_direction(f["boarding"], f["alighting"])
            result = engine.recommend(
                f["boarding"], f["alighting"], f["hour"], direction, f.get("dow", "MON")
            )
            scores_df = result["scores"]

            # Find the rank of the recommended car
            rec_car = f["recommended_car"]
            car_row = scores_df[scores_df["car"] == rec_car]

            if not car_row.empty:
                rank = int(car_row.iloc[0]["rank"])
                score = float(car_row.iloc[0]["score"])
                ranks_for_rec_car.append(rank)
                scores_for_rec_car.append(score)
                satisfactions_for_corr.append(f["satisfaction"])

                if f["satisfaction"] >= 4:
                    satisfied_scores.append(score)
                elif f["satisfaction"] <= 2:
                    unsatisfied_scores.append(score)

            # Check if best car matches actual car used
            actual_car = f.get("actual_car", rec_car)
            if result["best_car"] == actual_car:
                top1_hits += 1

        except Exception as e:
            logging.warning(
                "Validation: skipping feedback entry boarding=%s→%s hour=%d: %s",
                f.get("boarding"), f.get("alighting"), f.get("hour", -1), e,
            )
            skipped += 1
            continue

    top1_accuracy = top1_hits / n if n > 0 else 0.0

    # Spearman rank correlation between seatscore rank and satisfaction
    # BUG FIX: 이전에는 feedback[:len(ranks_for_rec_car)]를 사용하여
    # 건너뛴 항목이 있을 때 잘못된 인덱스를 참조했음
    rank_corr = None
    if len(ranks_for_rec_car) >= 5:
        try:
            from scipy.stats import spearmanr
            # Lower rank (better seat) should correlate with higher satisfaction
            corr, _ = spearmanr(ranks_for_rec_car, satisfactions_for_corr)
            rank_corr = round(float(corr), 4) if corr is not None else None
        except ImportError:
            # scipy not available - compute simple correlation
            rank_corr = None

    mean_score_sat = round(sum(satisfied_scores) / len(satisfied_scores), 2) if satisfied_scores else None
    mean_score_unsat = round(sum(unsatisfied_scores) / len(unsatisfied_scores), 2) if unsatisfied_scores else None

    return ValidationMetrics(
        total_feedback=n,
        mean_satisfaction=round(mean_sat, 2),
        seat_success_rate=round(seat_rate, 4),
        rank_correlation=rank_corr,
        top1_accuracy=round(top1_accuracy, 4),
        mean_score_satisfied=mean_score_sat,
        mean_score_unsatisfied=mean_score_unsat,
        skipped_count=skipped,
    )


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="모델 검증",
    description="사용자 피드백 데이터를 기반으로 SeatScore 모델의 정확도 지표를 산출합니다. "
               "SQLite에 저장된 피드백(use_db=True)을 사용하거나, "
               "요청 본문에 피드백 항목을 직접 전달할 수 있습니다.",
    response_description="검증 상태, 정확도 지표(mean_satisfaction, seat_success_rate, rank_correlation 등), 메시지",
)
async def validate_model(req: ValidationRequest):
    """
    Validate SeatScore model against user feedback.

    Can use stored feedback from SQLite (use_db=True) or
    accept feedback items directly in the request body.
    """
    try:
        if req.use_db:
            feedback = _load_feedback_from_db()
            if not feedback:
                return ValidationResponse(
                    status="no_data",
                    metrics=None,
                    message="No feedback data found in database. Submit feedback via /api/feedback first.",
                )
        else:
            if not req.feedback_items:
                return ValidationResponse(
                    status="no_data",
                    metrics=None,
                    message="No feedback items provided in request.",
                )
            feedback = [item.model_dump() for item in req.feedback_items]

        metrics = _compute_metrics(feedback)
        return ValidationResponse(
            status="ok",
            metrics=metrics,
            message=f"Validation complete with {metrics.total_feedback} feedback entries.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
