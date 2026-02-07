# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class RecommendRequest(BaseModel):
    boarding: str
    destination: str
    hour: int = Field(ge=0, le=23)
    direction: Optional[str] = None  # None이면 자동 판별


class CarScore(BaseModel):
    car: int
    score: float
    rank: int
    benefit: float
    penalty: float


class StationContribution(BaseModel):
    station: str
    D: float  # alighting volume
    T: float  # travel time
    w: float  # car weight
    contribution: float


class RecommendResponse(BaseModel):
    boarding: str
    destination: str
    hour: int
    direction: str
    alpha: float
    best_car: int
    best_score: float
    worst_car: int
    worst_score: float
    score_spread: float
    n_intermediate: int
    intermediates: List[str]
    car_scores: List[CarScore]
    boarding_congestion: Optional[float] = None
    data_sources: List[str] = []
    station_contributions: Optional[Dict[str, List[StationContribution]]] = None


class CalibrationRequest(BaseModel):
    beta: Optional[float] = Field(None, ge=0.0, le=2.0)
    escalator_weight: Optional[float] = Field(None, ge=0.1, le=5.0)
    elevator_weight: Optional[float] = Field(None, ge=0.1, le=5.0)
    stairs_weight: Optional[float] = Field(None, ge=0.1, le=5.0)
    alpha_morning_rush: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_evening_rush: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_midday: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_evening: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_night: Optional[float] = Field(None, ge=0.1, le=3.0)
    alpha_early: Optional[float] = Field(None, ge=0.1, le=3.0)


class CalibrationResponse(BaseModel):
    beta: float
    facility_weights: dict
    alpha_map: dict


class StationItem(BaseModel):
    name: str
    name_display: str  # 원래 역명 (역 접미사 포함)


class SensitivityPoint(BaseModel):
    beta: float
    car: int
    score: float
