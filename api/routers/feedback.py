# -*- coding: utf-8 -*-
"""
Feedback API Router
===================
Stores user feedback in SQLite and provides aggregated statistics.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import FeedbackRequest, FeedbackResponse, FeedbackStatsResponse, StationFeedbackStats

router = APIRouter()

DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "feedback.db"


_db_initialized = False


def _init_db():
    """Initialize database and create tables/indexes once."""
    global _db_initialized
    if _db_initialized:
        return
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            boarding TEXT NOT NULL,
            alighting TEXT NOT NULL,
            hour INTEGER NOT NULL,
            dow TEXT NOT NULL,
            recommended_car INTEGER NOT NULL,
            actual_car INTEGER NOT NULL,
            satisfaction INTEGER NOT NULL,
            got_seat INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        )
    """)
    # Indexes for common query patterns (stats aggregation, time-based queries)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_boarding ON feedback(boarding)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_hour ON feedback(hour)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at)")
    conn.commit()
    conn.close()
    _db_initialized = True


def _get_connection() -> sqlite3.Connection:
    """Get SQLite connection (database already initialized)."""
    _init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    summary="사용자 피드백 제출",
    description="추천 결과에 대한 사용자 피드백(만족도, 착석 여부, 실제 탑승 칸)을 "
    "SQLite에 저장합니다. 모델 검증에 활용됩니다.",
    response_description="저장된 피드백 ID",
)
async def submit_feedback(req: FeedbackRequest):
    """Store user feedback about seat recommendation accuracy."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO feedback
                (boarding, alighting, hour, dow, recommended_car, actual_car,
                 satisfaction, got_seat, comment, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.boarding,
                req.alighting,
                req.hour,
                req.dow,
                req.recommended_car,
                req.actual_car,
                req.satisfaction,
                1 if req.got_seat else 0,
                req.comment,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        feedback_id = cursor.lastrowid or 0
        return FeedbackResponse(id=feedback_id, message="피드백이 저장되었습니다")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"피드백 저장 실패: {str(e)}")
    finally:
        conn.close()


@router.get(
    "/feedback/stats",
    response_model=FeedbackStatsResponse,
    summary="피드백 통계 조회",
    description="전체 피드백 통계(평균 만족도, 착석 성공률)와 "
    "역별 집계 통계를 반환합니다.",
    response_description="전체 및 역별 피드백 통계",
)
async def get_feedback_stats():
    """Get aggregated feedback statistics."""
    conn = _get_connection()
    try:
        # Overall stats
        row = conn.execute(
            "SELECT COUNT(*) as cnt, AVG(satisfaction) as avg_sat, AVG(got_seat) as seat_rate FROM feedback"
        ).fetchone()

        total_count = row["cnt"]
        avg_satisfaction = round(row["avg_sat"], 2) if row["avg_sat"] else 0.0
        seat_success_rate = round(row["seat_rate"], 4) if row["seat_rate"] else 0.0

        # Per-station stats (by boarding station)
        station_rows = conn.execute(
            """
            SELECT boarding as station,
                   COUNT(*) as cnt,
                   AVG(satisfaction) as avg_sat,
                   AVG(got_seat) as seat_rate
            FROM feedback
            GROUP BY boarding
            ORDER BY cnt DESC
            """
        ).fetchall()

        per_station = [
            StationFeedbackStats(
                station=r["station"],
                count=r["cnt"],
                avg_satisfaction=round(r["avg_sat"], 2),
                seat_success_rate=round(r["seat_rate"], 4),
            )
            for r in station_rows
        ]

        return FeedbackStatsResponse(
            total_count=total_count,
            avg_satisfaction=avg_satisfaction,
            seat_success_rate=seat_success_rate,
            per_station=per_station,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")
    finally:
        conn.close()
