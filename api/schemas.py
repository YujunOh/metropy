from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any


VALID_DOW = Literal["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
VALID_DIRECTION = Literal["내선", "외선"]


class RecommendRequest(BaseModel):
    boarding: str = Field(max_length=20)
    destination: str = Field(max_length=20)
    hour: int = Field(ge=0, le=23)
    direction: Optional[VALID_DIRECTION] = None  # None이면 자동 판별
    dow: Optional[VALID_DOW] = None  # MON~SUN (None이면 평일 기본)


class CarScore(BaseModel):
    car: int
    score: float
    rank: int
    benefit: float
    penalty: float
    load_factor: float = 1.0  # 경쟁 계수: <1 비혼잡(끝호차), >1 혼잡(중간호차)
    estimated_seat_minutes: Optional[float] = None  # 기대착석시간 (분)
    p_seated: Optional[float] = None  # 목적지 도착 시 착석 확률 (0.0-1.0)


class StationContribution(BaseModel):
    station: str
    D: float  # alighting volume
    T: float  # travel time
    w: float  # car weight
    L: float = 1.0  # load factor (competition)
    L_eff: float = 1.0  # GAMMA-adjusted effective load factor
    contribution: float
    p_seated: Optional[float] = None  # 착석 확률
    p_sit: float = 1.0  # v4 engine field
    A: float = 0.0  # v4 engine field
    C: float = 0.0  # v4 engine field
    C_adj: float = 0.0  # GAMMA-adjusted competitors
    p_capture: float = 0.0  # v4 engine field
    p_first: float = 0.0  # v4 engine field


class RecommendResponse(BaseModel):
    boarding: str
    destination: str
    hour: int
    direction: str
    dow: Optional[str] = None
    alpha: float
    weather_factor: Optional[float] = None
    best_car: int
    best_score: float
    worst_car: int
    worst_score: float
    score_spread: float
    n_intermediate: int
    intermediates: List[str]
    car_scores: List[CarScore]
    boarding_congestion: Optional[float] = None
    load_factors: Optional[Dict[str, float]] = None  # {car_no: L(c)}
    data_sources: List[str] = []
    data_quality: Optional[Dict[str, str]] = None  # {source: exact|interpolated|fallback}
    station_contributions: Optional[Dict[str, List[StationContribution]]] = None
    best_seat_time: Optional[float] = None  # 최적 칸 기대착석시간 (분)
    p_seated_best: Optional[float] = None  # 최적 칸의 착석 확률


class CalibrationRequest(BaseModel):
    beta: Optional[float] = Field(None, ge=0.0, le=2.0)
    gamma: Optional[float] = Field(None, ge=0.0, le=1.0)  # 경쟁 계수 강도
    delta: Optional[float] = Field(None, ge=0.0, le=1.0)  # 초기 착석 보너스 강도
    escalator_weight: Optional[float] = Field(None, ge=0.1, le=5.0)
    elevator_weight: Optional[float] = Field(None, ge=0.0, le=5.0)
    stairs_weight: Optional[float] = Field(None, ge=0.1, le=5.0)
    alpha_morning_rush: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_evening_rush: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_midday: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_evening: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_night: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_early: Optional[float] = Field(None, ge=0.1, le=3.0)


class CalibrationResponse(BaseModel):
    beta: float
    gamma: float
    delta: float
    facility_weights: dict
    alpha_map: dict


class StationItem(BaseModel):
    name: str
    name_display: str  # 원래 역명 (역 접미사 포함)


class SensitivityPoint(BaseModel):
    beta: float
    car: int
    score: float


class SensitivityPointGamma(BaseModel):
    gamma: float
    car: int
    score: float


class SensitivityPointDelta(BaseModel):
    delta: float
    car: int
    score: float


# --- Feedback Schemas ---

class FeedbackRequest(BaseModel):
    boarding: str = Field(max_length=20)
    alighting: str = Field(max_length=20)
    hour: int = Field(ge=0, le=23)
    dow: VALID_DOW
    recommended_car: int = Field(ge=1, le=10)
    actual_car: int = Field(ge=1, le=10)
    satisfaction: int = Field(ge=1, le=5)
    got_seat: bool
    comment: Optional[str] = Field(None, max_length=500)


class FeedbackResponse(BaseModel):
    id: int
    message: str


class StationFeedbackStats(BaseModel):
    station: str
    count: int
    avg_satisfaction: float
    seat_success_rate: float


class FeedbackStatsResponse(BaseModel):
    total_count: int
    avg_satisfaction: float
    seat_success_rate: float
    per_station: List[StationFeedbackStats]


# --- Nearest Station Schemas ---

class NearestStationItem(BaseModel):
    name: str
    code: str
    distance_m: float
    lat: float
    lng: float


class NearestStationResponse(BaseModel):
    stations: List[NearestStationItem]

# --- Validation Schemas ---

class ValidationFeedbackItem(BaseModel):
    boarding: str
    alighting: str
    hour: int = Field(ge=0, le=23)
    dow: str = 'MON'
    recommended_car: int = Field(ge=1, le=10)
    satisfaction: int = Field(ge=1, le=5)
    got_seat: bool


class ValidationRequest(BaseModel):
    feedback_items: Optional[List[ValidationFeedbackItem]] = None
    use_db: bool = True  # If True, load from SQLite; if False, use feedback_items


class ValidationMetrics(BaseModel):
    total_feedback: int
    mean_satisfaction: float
    seat_success_rate: float
    rank_correlation: Optional[float] = None  # Spearman correlation: seatscore rank vs satisfaction
    top1_accuracy: float  # How often recommended car == user's actual best
    mean_score_satisfied: Optional[float] = None  # Avg seatscore for satisfied users (4-5)
    mean_score_unsatisfied: Optional[float] = None  # Avg seatscore for unsatisfied users (1-2)
    skipped_count: int = 0


class ValidationResponse(BaseModel):
    status: str
    metrics: Optional[ValidationMetrics] = None
    message: str


# --- Rank Stability Schemas ---

class RankStabilityCarResult(BaseModel):
    car: int
    base_rank: int
    base_score: float
    rank_changes: int  # how many times rank changed across perturbations
    min_rank: int
    max_rank: int
    avg_score: float
    score_std: float

class RankStabilityResponse(BaseModel):
    boarding: str
    destination: str
    hour: int
    direction: str
    n_perturbations: int
    best_car_stable: bool  # True if best car never changed
    best_car_change_pct: float  # % of perturbations where best car changed
    cars: List[RankStabilityCarResult]
