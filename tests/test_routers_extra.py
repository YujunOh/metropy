# pyright: reportMissingTypeStubs=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportPrivateUsage=false, reportPrivateLocalImportUsage=false, reportUnannotatedClassAttribute=false, reportAny=false, reportUnusedParameter=false, reportUnknownLambdaType=false
"""validate/stability/feedback 라우터 추가 테스트"""
import asyncio
import sqlite3
import threading
from dataclasses import dataclass

import pandas as pd

from api.routers import feedback, stability, validate
from api.schemas import FeedbackRequest, ValidationRequest


class _FakeValidateEngine:
    def recommend(self, boarding, alighting, hour, direction, dow):
        if boarding == "오류역":
            raise ValueError("invalid station")

        scores = pd.DataFrame([
            {"car": 1, "rank": 1, "score": 88.0},
            {"car": 2, "rank": 2, "score": 72.0},
            {"car": 3, "rank": 3, "score": 60.0},
        ])
        return {"scores": scores, "best_car": 1}


def test_compute_metrics_tracks_skipped_count(monkeypatch):
    """예외 항목을 건너뛰고 skipped_count를 집계한다."""
    engine = _FakeValidateEngine()
    monkeypatch.setattr(validate.registry, "get_engine", lambda: engine)
    monkeypatch.setattr(validate.registry, "auto_direction", lambda *_: "내선")

    feedback_rows = [
        {
            "boarding": "강남",
            "alighting": "시청",
            "hour": 8,
            "dow": "MON",
            "recommended_car": 1,
            "actual_car": 1,
            "satisfaction": 5,
            "got_seat": True,
        },
        {
            "boarding": "오류역",
            "alighting": "시청",
            "hour": 8,
            "dow": "MON",
            "recommended_car": 2,
            "actual_car": 2,
            "satisfaction": 1,
            "got_seat": False,
        },
    ]

    metrics = validate._compute_metrics(feedback_rows)

    assert metrics.total_feedback == 2
    assert metrics.skipped_count == 1
    assert metrics.top1_accuracy == 0.5
    assert metrics.mean_score_satisfied == 88.0


def test_validate_endpoint_returns_no_data_without_items():
    """요청 데이터가 없으면 no_data 상태를 반환한다."""
    req = ValidationRequest(use_db=False, feedback_items=None)
    result = asyncio.run(validate.validate_model(req))

    assert result.status == "no_data"
    assert result.metrics is None


@dataclass(frozen=True)
class _FakeParams:
    alpha_map: dict[str, float]


class _FakeStabilityEngine:
    def __init__(self):
        self.params = _FakeParams(alpha_map={"morning_rush": 1.4, "midday": 1.0})

    def compute_seatscore(self, boarding, destination, hour, direction):
        # 점수 차이를 고정해 perturbation에서도 순위가 유지되도록 구성
        rows = [
            {"car": c, "rank": c, "score": float(110 - c)}
            for c in range(1, 11)
        ]
        return pd.DataFrame(rows)


def test_rank_stability_endpoint_shape(monkeypatch):
    """stability 엔드포인트가 기대 스키마를 반환한다."""
    engine = _FakeStabilityEngine()
    monkeypatch.setattr(stability.registry, "get_engine", lambda: engine)
    monkeypatch.setattr(stability.registry, "auto_direction", lambda *_: "내선")
    monkeypatch.setattr(stability.registry, "engine_lock", threading.RLock(), raising=False)

    result = asyncio.run(stability.rank_stability(
        boarding="강남", destination="시청", hour=8, n_perturbations=5
    ))

    assert result.n_perturbations == 5
    assert result.best_car_stable is True
    assert result.best_car_change_pct == 0.0
    assert len(result.cars) == 10
    assert result.cars[0].car == 1


def test_feedback_submit_and_stats_with_temp_sqlite(tmp_path, monkeypatch):
    """피드백 저장과 통계 집계를 임시 DB에서 검증한다."""
    test_db = tmp_path / "feedback.db"
    monkeypatch.setattr(feedback, "DB_PATH", test_db)
    monkeypatch.setattr(feedback, "_db_initialized", False)

    req = FeedbackRequest(
        boarding="강남",
        alighting="시청",
        hour=8,
        dow="MON",
        recommended_car=1,
        actual_car=1,
        satisfaction=5,
        got_seat=True,
        comment="정확함",
    )

    submit_result = asyncio.run(feedback.submit_feedback(req))
    stats = asyncio.run(feedback.get_feedback_stats())

    assert submit_result.id >= 1
    assert test_db.exists()
    assert stats.total_count == 1
    assert stats.avg_satisfaction == 5.0
    assert stats.seat_success_rate == 1.0
    assert stats.per_station[0].station == "강남"

    conn = sqlite3.connect(str(test_db))
    try:
        row = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()
        assert row[0] == 1
    finally:
        conn.close()
