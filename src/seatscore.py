# -*- coding: utf-8 -*-
"""
SeatScore Decision Model v4
============================
Probability-based utility model for per-car seating recommendation on Seoul Metro Line 2.

Formula (v4):
    U(c) = Σ_s [ p_first(c,s) × T(s→dest) ] + δ·max(0,1-L_eff)·T_total - β·B(c,h)·T_total

    Where:
        p_capture(c,s) = 1 - exp(-A_freed / (ε + C_adj))
        A_freed        = D(s) × w(c,s) × p_sit(s) × α(h)
        C_adj          = C_competitors × L_eff(c)
        L_eff          = (L_raw ^ γ) / mean(L_raw ^ γ)     [GAMMA-dampened load factor]
        p_first(c,s)   = p_capture × Π(1 - p_prev)          [first-capture probability]

Components:
    D(s)          : alighting volume at intermediate station s
                    Source: 서울교통공사 혼잡도 (30-min, direction-aware)
    T(s→dest)     : remaining travel time from s to destination (seat-time benefit)
    w(c,s)        : per-car alighting distribution at station s
                    Source: SK API getOffCarRate (fallback: fast-exit facility weight)
    α(h)          : time-of-day congestion multiplier (calibratable via ALPHA_MAP)
    B(c,h)        : boarding congestion penalty per car
                    Source: SK API congestionCar (fallback: facility weight)
    β (BETA)      : penalty coefficient for boarding crowding
    γ (GAMMA)     : competition factor dampening (L^γ compresses load factor spread)
    δ (DELTA)     : initial seat availability bonus for less-crowded cars

v4 improvements over v3:
    - Probability-based scoring: p_capture/p_first model replaces deterministic benefit sum
    - GAMMA: load factor compression (L^γ) with re-normalization
    - DELTA: initial seat availability bonus for end cars
    - BETA penalty reintegrated: β·B(c,h)·T_total subtracted from raw score
    - Competitor turnover: competitors who sat at earlier stations reduce future competition
    - DOW factor applied to competitors (not just alighting volume)
    - Adaptive sigmoid normalization (steepness 3-5 based on raw score spread)
    - α(h) anchors derived from ALPHA_MAP → user calibration actually affects scoring
    - 30-min granularity congestion data (5 quarterly files, 2024-2025)
    - Direction-aware congestion (내선/외선 separate)
    - SK API data hooks (car congestion, alighting rates, train congestion)
    - Per-station contribution data for explanation UI
    - Day-type awareness (weekday/weekend)
    - Graceful fallback: SK API data → facility data → uniform
    - getoff_rate & car_congestion: 100% complete (817 entries each, all weekday hours)
    - train_congestion: rush hours only (248 entries), uses interpolation for off-peak
"""

import json
import logging
import pickle
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

try:
    from src.utils import normalize_station_name
except ImportError:
    from utils import normalize_station_name


# pickle 보안: 허용된 타입만 로드 (임의 코드 실행 방지)
PICKLE_SAFE_MODULES = {
    'builtins': {'dict', 'list', 'tuple', 'set', 'frozenset', 'int', 'float',
                  'str', 'bytes', 'bool', 'complex', 'type', 'NoneType', 'range',
                  'slice', 'bytearray'},
    'collections': {'OrderedDict', 'defaultdict', 'Counter'},
    'numpy': {'ndarray', 'dtype', 'float64', 'float32', 'int64', 'int32',
              'bool_', 'array', 'str_'},
    'numpy.core.multiarray': {'scalar', '_reconstruct'},
    'numpy.core.numeric': {'*'},
    'numpy.ma.core': {'MaskedArray'},
    '_codecs': {'encode'},
}


class RestrictedUnpickler(pickle.Unpickler):
    """pickle 로드 시 허용된 모듈/클래스만 허용하는 보안 언피클러"""

    def find_class(self, module: str, name: str):
        if module in PICKLE_SAFE_MODULES:
            allowed = PICKLE_SAFE_MODULES[module]
            if '*' in allowed or name in allowed:
                return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"보안 위반: {module}.{name} 로드 차단됨"
        )


def safe_pickle_load(filepath):
    """보안 강화된 pickle 로드 — RestrictedUnpickler 사용"""
    with open(filepath, 'rb') as f:
        return RestrictedUnpickler(f).load()

@dataclass(frozen=True)
class SeatScoreParams:
    beta: float = 0.3
    gamma: float = 0.5
    delta: float = 0.15
    facility_weights: Dict[str, float] = field(default_factory=lambda: {
        "에스컬레이터": 1.2,
        "엘리베이터": 0.0,
        "계단": 1.0,
    })
    alpha_map: Dict[str, float] = field(default_factory=lambda: {
        "morning_rush": 1.4,
        "evening_rush": 1.3,
        "midday": 1.0,
        "evening": 0.9,
        "night": 0.6,
        "early": 0.5,
    })


# ---------------------------------------------------------------------------
# SeatScore Engine v4
# ---------------------------------------------------------------------------

class SeatScoreEngine:
    """
    Compute per-car seating utility scores for a given trip on Line 2.

    v4 probability-based model with:
    - p_capture/p_first seat probability at each intermediate station
    - GAMMA-dampened load factor competition model
    - DELTA initial seat availability bonus
    - BETA boarding penalty reintegration
    - Competitor turnover tracking
    - DOW-scaled competitor counts

    Data sources:
    - 서울교통공사 혼잡도 30-min data (congestion_30min.csv)
    - Seoul Fast Exit API data (fast_exit_line2.json)
    - SK Open API car-level data (when available)
    - Interstation distance data

    Graceful degradation: works with any subset of data available.
    """

    TOTAL_CARS = 10  # Line 2 uses 10-car trains

    # Empirical per-car alighting distribution from SK API data
    # Derived from 195 getoff_rate entries across 41 Line 2 stations
    # Remarkably consistent across stations and time periods
    EMPIRICAL_CAR_DIST = [
        0.088, 0.102, 0.111, 0.116, 0.111,
        0.104, 0.109, 0.099, 0.085, 0.074,
    ]

    # Per-car physical constants
    SEATS_PER_CAR = 54      # seated capacity per car (Line 2 standard)
    MAX_CAPACITY = 160      # total capacity per car at 100% congestion

    def __init__(self, data_dir="data/processed", raw_dir="data/raw"):
        self.data_dir = Path(data_dir)
        self.raw_dir = Path(raw_dir)

        self.fast_exit_df = None
        self.congestion_df = None
        self.distance_df = None
        self.station_order = []

        # precomputed caches
        self._facility_cache = {}
        self._station_dir_total = {}
        self._exit_count_cache = {}  # (station, direction) → [10 exit counts per car]
        self._alighting_cache = {}
        self._congestion_30min_cache = {}   # (station, direction, hour) → congestion %
        self._car_congestion_cache = None   # SK API: (station, hour, dow) → [10 values]
        self._getoff_rate_cache = None      # SK API: (station, hour, dow) → [10 values]
        self._train_congestion_cache = None # SK API: (station, hour, dow) → value
        self._travel_time_matrix = None     # TMAP: station→station → seconds
        self._exit_traffic_cache = {}       # exit traffic: (station, dow) → {exit_no: count}

        # data source tracking
        self.data_sources = {}
        self._weather_service = None
        self.params = SeatScoreParams()

    def set_weather_service(self, weather_service):
        self._weather_service = weather_service

    # ----- loading -----------------------------------------------------------

    def load_all(self):
        self._load_fast_exit()
        self._load_congestion()
        self._load_congestion_30min()
        self._load_distance()
        self._build_facility_cache()
        self._load_sk_data()
        self._load_travel_times()
        self._load_exit_traffic()
        logging.info("SeatScoreEngine v4: all data loaded.")
        logging.info(f"  Data sources: {self.data_sources}")

    def _load_fast_exit(self):
        json_path = self.raw_dir / "fast_exit_line2.json"
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        df = pd.DataFrame(data)
        df["station_normalized"] = df["stnNm"].apply(normalize_station_name)
        df["car_no"] = df["qckgffVhclDoorNo"].apply(
            lambda x: int(str(x).split("-")[0]) if pd.notna(x) and "-" in str(x) else None
        )
        df["door_no"] = df["qckgffVhclDoorNo"].apply(
            lambda x: int(str(x).split("-")[1]) if pd.notna(x) and "-" in str(x) else None
        )
        self.fast_exit_df = df
        self.data_sources["fast_exit"] = len(df)
        print(f"  Fast Exit: {len(df)} records, "
              f"{df['station_normalized'].nunique()} stations")

    def _load_congestion(self):
        csv_path = self.data_dir / "congestion_long.csv"
        pkl_path = self.data_dir / "alighting_cache.pkl"

        # pickle 캐시가 있으면 우선 로드 (CSV 없어도 동작)
        if pkl_path.exists():
            csv_newer = csv_path.exists() and csv_path.stat().st_mtime > pkl_path.stat().st_mtime
            if not csv_newer:
                self._alighting_cache = safe_pickle_load(pkl_path)
                self.congestion_df = None
                self.data_sources["alighting_cache"] = len(self._alighting_cache)
                print(f"  Congestion cache: {len(self._alighting_cache)} entries (from pickle)")
                return

        if not csv_path.exists():
            raise FileNotFoundError(
                f"congestion_long.csv 또는 alighting_cache.pkl이 필요합니다: {self.data_dir}"
            )

        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        self.congestion_df = df

        # 하차량 lookup 캐시 구축 (성능 최적화)
        alight = df[df["type"] == "alighting"]
        self._alighting_cache = alight.groupby(["station_normalized", "hour"])["count"].mean().to_dict()

        # pickle 저장
        try:
            with open(pkl_path, "wb") as f:
                pickle.dump(self._alighting_cache, f)
        except OSError:
            print("  Warning: pickle 캐시 저장 실패 (read-only filesystem)")

        self.congestion_df = None  # 메모리 절약
        self.data_sources["alighting_cache"] = len(self._alighting_cache)
        print(f"  Congestion: {len(df):,} records -> cache: {len(self._alighting_cache)} entries")

    def _load_congestion_30min(self):
        """Load 30-min granularity direction-aware congestion data."""
        csv_path = self.data_dir / "congestion_30min.csv"
        if not csv_path.exists():
            print("  Congestion 30min: not found (skipping)")
            return

        df = pd.read_csv(csv_path, encoding="utf-8-sig")

        # Build lookup cache: (station, direction, hour) → congestion %
        for _, row in df.iterrows():
            station = row.get("station_normalized", "")
            direction = row.get("direction", "")
            hour = int(row.get("hour", 0))
            congestion = row.get("congestion_weighted_avg", 0)

            if station and hour >= 0:
                key = (station, direction, hour)
                if key in self._congestion_30min_cache:
                    # Average across minute slots
                    self._congestion_30min_cache[key] = (
                        self._congestion_30min_cache[key] + congestion
                    ) / 2
                else:
                    self._congestion_30min_cache[key] = congestion

        self.data_sources["congestion_30min"] = len(self._congestion_30min_cache)
        print(f"  Congestion 30min: {len(self._congestion_30min_cache)} entries")

    def _load_distance(self):
        csv_path = self.data_dir / "interstation_distance_processed.csv"
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
        df["station_normalized"] = df.iloc[:, 2].apply(normalize_station_name)
        self.distance_df = df
        self.station_order = df["station_normalized"].tolist()
        self.data_sources["distance"] = len(df)
        print(f"  Distance: {len(df)} segments, {len(self.station_order)} stations")

    def _build_facility_cache(self):
        """
        Precompute per (station, direction, car) facility score,
        and per (station, direction) exit count distribution.
        """
        if self.fast_exit_df is None:
            return

        df = self.fast_exit_df.copy()

        # map facility names to weights
        df["fac_weight"] = df["plfmCmgFac"].map(self.params.facility_weights).fillna(1.0)

        grouped = df.groupby(
            ["station_normalized", "upbdnbSe", "car_no"]
        )["fac_weight"].sum()

        self._facility_cache = grouped.to_dict()

        # also compute per-station-direction total for normalization
        self._station_dir_total = df.groupby(
            ["station_normalized", "upbdnbSe"]
        )["fac_weight"].sum().to_dict()

        # Build exit count cache: (station, direction) → [10 exit counts]
        # Used by _get_empirical_weight for station-specific adjustment
        exit_counts = df.groupby(
            ["station_normalized", "upbdnbSe", "car_no"]
        ).size()
        for (station, direction), group in df.groupby(
            ["station_normalized", "upbdnbSe"]
        ):
            counts = [0] * self.TOTAL_CARS
            for _, row in group.iterrows():
                car = row.get("car_no")
                if car and 1 <= car <= self.TOTAL_CARS:
                    counts[int(car) - 1] += 1
            self._exit_count_cache[(station, direction)] = counts

        self.data_sources["facility_cache"] = len(self._facility_cache)
        print(f"  Facility cache: {len(self._facility_cache)} entries, "
              f"exit count cache: {len(self._exit_count_cache)} station-directions")

    def _load_sk_data(self):
        """Load SK Open API data caches if available."""
        sk_files = {
            "car_congestion_cache": "_car_congestion_cache",
            "getoff_rate_cache": "_getoff_rate_cache",
            "train_congestion_cache": "_train_congestion_cache",
        }

        for filename, attr in sk_files.items():
            pkl_path = self.data_dir / f"{filename}.pkl"
            if pkl_path.exists():
                cache = safe_pickle_load(pkl_path)
                setattr(self, attr, cache)
                self.data_sources[f"sk_{filename}"] = len(cache)
                print(f"  SK {filename}: {len(cache)} entries")
            else:
                print(f"  SK {filename}: not found (using fallback)")

    def _load_travel_times(self):
        """Load TMAP transit cumulative travel times if available."""
        cum_path = self.data_dir / "cumulative_times.pkl"
        if cum_path.exists():
            cum_data = safe_pickle_load(cum_path)
            self._tt_stations = cum_data["stations"]  # ordered station names
            self._tt_cumulative = cum_data["cumulative"]  # cumulative seconds
            n = len(self._tt_stations)
            self.data_sources["travel_times"] = n
            print(f"  Travel times: {n} stations (cumulative, direction-aware)")
        else:
            self._tt_stations = []
            self._tt_cumulative = []
            print(f"  Travel times: not found (using distance fallback)")

    def _load_exit_traffic(self):
        """Load exit traffic statistics and build day-of-week correction factors."""
        pkl_path = self.data_dir / "exit_traffic_cache.pkl"
        if pkl_path.exists():
            self._exit_traffic_cache = safe_pickle_load(pkl_path)
            self._build_dow_factors()
            self.data_sources["exit_traffic"] = len(self._exit_traffic_cache)
            print(f"  Exit traffic: {len(self._exit_traffic_cache)} entries")
        else:
            print(f"  Exit traffic: not found (using facility fallback)")

    def _build_dow_factors(self):
        """
        Build per-station day-of-week correction factors from exit traffic.

        dow_factor(station, dow) = traffic(station, dow) / avg_weekday_traffic(station)

        Examples:
        - 강남 Saturday: 0.59 (much quieter on weekends)
        - 홍대입구 Saturday: 1.29 (busier on weekends)
        """
        self._dow_factors = {}  # (station, dow) → float ratio

        # Collect per-station totals by day
        station_day_totals = {}
        for (station, dow), exits in self._exit_traffic_cache.items():
            total = sum(exits.values())
            if station not in station_day_totals:
                station_day_totals[station] = {}
            station_day_totals[station][dow] = total

        # Compute correction factor: ratio to weekday average
        weekday_codes = ["MON", "TUE", "WED", "THU", "FRI"]
        for station, day_data in station_day_totals.items():
            weekday_vals = [day_data[d] for d in weekday_codes if d in day_data]
            if not weekday_vals:
                continue
            weekday_avg = sum(weekday_vals) / len(weekday_vals)
            if weekday_avg <= 0:
                continue
            for dow, total in day_data.items():
                self._dow_factors[(station, dow)] = total / weekday_avg

    # ----- core logic --------------------------------------------------------

    def _get_alpha(self, hour, params=None):
        """
        Time-of-day congestion multiplier using smooth interpolation.

        Uses a continuous function instead of discrete buckets for smoother
        transitions between time periods. Peak at 8am (morning rush) and
        6:30pm (evening rush), with gradual decay towards night hours.

        **IMPORTANT**: Anchor values are derived from self.ALPHA_MAP so that
        user calibration (via /api/calibrate) actually affects scoring.
        The shape of the interpolation curve is fixed; the peak/trough
        amplitudes come from ALPHA_MAP.
        """
        # Read calibrated values (users can change these via /api/calibrate)
        active_params = params if params is not None else self.params
        alpha_map = active_params.alpha_map
        a_morning = alpha_map.get("morning_rush", 1.4)
        a_evening = alpha_map.get("evening_rush", 1.3)
        a_midday = alpha_map.get("midday", 1.0)
        a_eve = alpha_map.get("evening", 0.9)
        a_night = alpha_map.get("night", 0.6)
        a_early = alpha_map.get("early", 0.5)

        # Build anchors from calibrated values
        # Transition points use linear blends between adjacent periods
        anchors = [
            (0, a_night),                                    # midnight
            (4, a_early),                                    # early morning
            (6, (a_early + a_midday) / 2),                   # ramping up
            (7, (a_midday + a_morning) / 2),                 # building to rush
            (8, a_morning),                                  # morning rush peak
            (9, (a_morning + a_midday) / 2),                 # post-rush
            (10, a_midday),                                  # midday start
            (12, a_midday),                                  # lunch
            (14, a_midday),                                  # afternoon
            (17, (a_midday + a_evening) / 2),                # building to evening rush
            (18, a_evening),                                 # evening rush starts
            (19, (a_evening + a_evening) / 2 * 1.04),        # evening rush peak (~+4%)
            (20, (a_evening + a_eve) / 2),                   # post-rush
            (21, a_eve),                                     # evening
            (22, (a_eve + a_night) / 2),                     # late evening
            (23, a_night),                                   # night
            (24, a_night),                                   # wrap to midnight
        ]

        h = hour % 24

        for i in range(len(anchors) - 1):
            h1, a1 = anchors[i]
            h2, a2 = anchors[i + 1]
            if h1 <= h < h2:
                ratio = (h - h1) / (h2 - h1)
                return round(a1 + ratio * (a2 - a1), 2)

        return alpha_map.get("midday", 1.0)

    def _get_intermediate_stations(self, boarding, destination, direction):
        stations = self.station_order
        if not stations:
            return []

        def find_idx(name):
            try:
                return stations.index(name)
            except ValueError:
                for i, s in enumerate(stations):
                    if name in s or s in name:
                        return i
                return -1

        b_idx = find_idx(boarding)
        d_idx = find_idx(destination)

        if b_idx < 0 or d_idx < 0:
            return []

        n = len(stations)
        is_inner = "내선" in str(direction) or "하행" in str(direction)

        if is_inner:
            if d_idx > b_idx:
                return stations[b_idx + 1: d_idx + 1]
            else:
                return stations[b_idx + 1:] + stations[:d_idx + 1]
        else:
            if d_idx < b_idx:
                return stations[d_idx: b_idx][::-1]
            else:
                return (stations[:b_idx][::-1] + stations[d_idx:][::-1])

    def _get_dow_factor(self, station, dow=None):
        """
        Day-of-week correction factor based on exit traffic data.

        Returns a multiplier (e.g., 0.59 for 강남 on weekend, 1.29 for 홍대입구).
        Defaults to 1.0 if no data or weekday.
        """
        if not dow or not hasattr(self, "_dow_factors") or not self._dow_factors:
            return 1.0
        return self._dow_factors.get((station, dow), 1.0)

    def _get_alighting_volume(self, station, hour, direction=None, dow=None):
        """
        D(s): alighting volume at station s during hour h.

        Priority:
        1. Direction-aware 30-min congestion data (if available)
        2. Hourly alighting cache (backward compatible)
        3. Fallback: 1.0

        Adjusted by day-of-week factor from exit traffic when dow is provided.
        """
        # Try direction-aware 30-min data first
        if self._congestion_30min_cache and direction:
            dir_key = "내선" if ("내선" in str(direction) or "하행" in str(direction)) else "외선"
            val = self._congestion_30min_cache.get((station, dir_key, hour))
            if val is not None:
                return val * self._get_dow_factor(station, dow)

            # Try without direction specificity
            for key, v in self._congestion_30min_cache.items():
                if key[0] == station and key[2] == hour:
                    return v * self._get_dow_factor(station, dow)

        # Fallback to hourly cache
        base = self._alighting_cache.get((station, hour), 1.0)
        return base * self._get_dow_factor(station, dow)

    def _get_travel_time(self, station_from, station_to, direction=None):
        """
        T(s->dest): remaining travel time from station s to destination.

        Direction-aware: on circular Line 2, the travel time depends on
        which direction the train is going (inner/clockwise vs outer).

        Priority:
        1. TMAP transit cumulative times (real seconds, direction-aware)
        2. Distance-based proxy (km, backward compatible)
        """
        # Try TMAP cumulative travel times
        if self._tt_stations and self._tt_cumulative:
            try:
                idx_from = self._tt_stations.index(station_from)
                idx_to = self._tt_stations.index(station_to)
            except ValueError:
                pass
            else:
                cum = self._tt_cumulative
                total_loop = cum[-1]  # full loop time in seconds

                # Inner (clockwise): cum[to] - cum[from], wrapping around
                inner_time = (cum[idx_to] - cum[idx_from]) % total_loop
                outer_time = total_loop - inner_time

                is_inner = direction and (
                    "내선" in str(direction) or "하행" in str(direction)
                )

                if direction:
                    tt_sec = inner_time if is_inner else outer_time
                else:
                    tt_sec = min(inner_time, outer_time)

                return max(tt_sec / 60.0, 0.1)  # seconds → minutes

        # Fallback to distance-based proxy
        if self.distance_df is None:
            return 1.0
        try:
            idx_from = self.station_order.index(station_from)
            idx_to = self.station_order.index(station_to)
        except ValueError:
            return 1.0

        cum = self.distance_df["cumulative_distance"].values
        if idx_from < len(cum) and idx_to < len(cum):
            return abs(cum[idx_to] - cum[idx_from]) + 0.1
        return 1.0

    def _resolve_sk_key(self, station, hour, dow=None):
        """
        Resolve the best available SK API cache key for (station, hour, dow).

        Priority:
        1. Exact (station, hour, dow) match
        2. Weekday fallback: (station, hour, "MON") for weekday dow
        3. Nearest rush hour: interpolate from closest rush-hour data
        """
        dow_key = dow if dow else "MON"
        # Weekdays share similar patterns → fallback to MON
        weekday_codes = ("MON", "TUE", "WED", "THU", "FRI")
        if dow_key in weekday_codes:
            dow_key = "MON"

        return station, hour, dow_key

    def _find_nearest_rush_data(self, cache, station, hour, dow_key):
        """
        When exact hour not in cache, find nearest rush hour data and interpolate.

        Rush hours in cache: 7, 8, 9, 17, 18, 19
        For non-rush hours, blend nearest rush data with distance-based decay.

        NOTE: As of 2025, getoff_rate and car_congestion are 100% complete for
        weekday hours, so this method is primarily used for train_congestion
        (248 entries, rush hours only). Kept for backward compatibility and
        non-weekday queries.
        """
        if not cache:
            return None

        rush_hours = [7, 8, 9, 17, 18, 19]
        # Find nearest rush hour with data
        best_hour = None
        best_dist = 999
        for rh in rush_hours:
            data = cache.get((station, rh, dow_key))
            if data:
                dist = abs(hour - rh)
                if dist < best_dist:
                    best_dist = dist
                    best_hour = rh

        if best_hour is None:
            return None

        data = cache.get((station, best_hour, dow_key))
        if data is None:
            return None

        # Decay factor: farther from rush hour → blend toward uniform
        # 0 hours away → 1.0 (full data), 6+ hours → 0.3 (mostly uniform)
        decay = max(0.3, 1.0 - best_dist * 0.12)
        return data, decay

    def _get_car_weight(self, station, car_no, direction, hour=None, dow=None):
        """
        w(c,s): per-car alighting weight at station s.

        As of 2025, SK API getoff_rate data is 100% complete for all 43 stations
        x 19 hours (05-23) on weekdays (817 entries). Direct lookup should always
        succeed for weekday queries. Fallback chain retained for non-weekday dow
        or unexpected edge cases.

        Priority:
        1. SK API getOffCarRate - exact match (should always hit for MON)
        2. Empirical distribution + exit count adjustment (fallback)
        """
        # SK API getoff rate - complete coverage for weekday hours
        if self._getoff_rate_cache and hour is not None:
            _, h, dk = self._resolve_sk_key(station, hour, dow)
            rates = self._getoff_rate_cache.get((station, h, dk))
            if rates and len(rates) == self.TOTAL_CARS:
                total = sum(rates)
                if total > 0:
                    return rates[car_no - 1] / total
                return 1.0 / self.TOTAL_CARS

        # Fallback: empirical distribution adjusted by exit count
        # (only reached for non-weekday dow or missing cache)
        return self._get_empirical_weight(station, car_no, direction)

    def _get_empirical_weight(self, station, car_no, direction):
        """
        Empirically-derived per-car weight, adjusted by station exit layout.

        Uses the global alighting distribution from SK API data (195 entries,
        41 stations) as a prior, then adjusts based on how many exits are
        near each car at this station (correlation r=0.45).

        Much more realistic than arbitrary facility-type heuristics.
        """
        base = self.EMPIRICAL_CAR_DIST[car_no - 1]

        # Station-specific exit count adjustment
        dir_key = "하행" if ("내선" in str(direction) or "하행" in str(direction)) else "상행"
        exit_counts = self._exit_count_cache.get((station, dir_key))

        if exit_counts:
            total_exits = sum(exit_counts)
            if total_exits > 0:
                # This car's exit proportion vs uniform expectation
                car_exit_pct = exit_counts[car_no - 1] / total_exits
                uniform_pct = 1.0 / self.TOTAL_CARS
                # Blend: 30% weight on exit count signal (based on r=0.45)
                adjustment = 0.3 * (car_exit_pct - uniform_pct)
                base = max(0.01, base + adjustment)

        return base

    def _get_facility_score(self, station, car_no, direction):
        """
        Facility-based structural weight for car c at station s.

        Returns a value from [0, 1] range.
        """
        dir_key = "하행" if ("내선" in str(direction) or "하행" in str(direction)) else "상행"

        car_score = self._facility_cache.get((station, dir_key, car_no), 0.0)
        total_score = self._station_dir_total.get((station, dir_key), 1.0)

        if total_score <= 0:
            return 1.0 / self.TOTAL_CARS  # uniform if no data

        return car_score / total_score

    def _get_boarding_penalty(self, car_no, boarding_station, hour, direction, dow=None):
        """
        B(c,h): boarding congestion penalty per car.

        As of 2025, SK API car_congestion data is 100% complete for all 43 stations
        x 19 hours (05-23) on weekdays (817 entries). Direct lookup should always
        succeed for weekday queries.

        Priority:
        1. SK API congestionCar - exact match (should always hit for MON)
        2. Facility-based estimation (fallback for non-weekday or missing cache)

        When train_congestion data is available, it scales the penalty
        by the actual train-level crowding (higher train congestion → bigger penalty).
        """
        base_penalty = None

        # SK API car congestion - complete coverage for weekday hours
        if self._car_congestion_cache and hour is not None:
            _, h, dk = self._resolve_sk_key(boarding_station, hour, dow)
            congestion = self._car_congestion_cache.get((boarding_station, h, dk))
            if congestion and len(congestion) == self.TOTAL_CARS:
                total = sum(congestion)
                if total > 0:
                    base_penalty = congestion[car_no - 1] / total

        if base_penalty is None:
            # Fallback: facility-based estimation
            # (only reached for non-weekday dow or missing cache)
            base_penalty = self._get_facility_score(boarding_station, car_no, direction)

        # Scale by train-level congestion if available
        # (train_congestion still uses _find_nearest_rush_data: only 248 rush-hour entries)
        train_scale = self._get_train_congestion_scale(boarding_station, hour, dow)
        return base_penalty * train_scale

    def _get_train_congestion_scale(self, station, hour, dow=None):
        """
        Use train-level congestion to scale penalties/factors.

        Returns a multiplier around 1.0:
        - train congestion > average → scale > 1.0 (more crowded)
        - train congestion < average → scale < 1.0 (less crowded)
        - no data → 1.0 (neutral)

        Average train congestion across all cached data is ~50 (typical %),
        so we normalize relative to that baseline.
        """
        if not self._train_congestion_cache:
            return 1.0

        _, h, dk = self._resolve_sk_key(station, hour, dow)
        tc = self._train_congestion_cache.get((station, h, dk))

        # Try nearest rush hour if exact not found
        if tc is None:
            result = self._find_nearest_rush_data(
                self._train_congestion_cache, station, hour, dk
            )
            if result:
                tc, decay = result
                # For scalar values, blend toward baseline (50)
                tc = decay * tc + (1 - decay) * 50.0

        if tc is None:
            return 1.0

        # Normalize: 50% is baseline → scale=1.0, 70% → 1.4, 30% → 0.6
        baseline = 50.0
        scale = tc / baseline if baseline > 0 else 1.0
        # Clamp to reasonable range [0.5, 2.0]
        return max(0.5, min(2.0, scale))

    def _get_sitting_fraction(self, station, hour, direction=None, dow=None):
        """
        Estimate what fraction of alighting passengers were seated.

        Uses train-level congestion as a proxy:
        - low congestion: most alighters were seated (~0.85)
        - high congestion: seat-limited floor (~54/160 ≈ 0.34)
        """
        SEATS_PER_CAR = 54
        MAX_CAPACITY = 160
        MIN_SIT_FRACTION = SEATS_PER_CAR / MAX_CAPACITY

        scale = self._get_train_congestion_scale(station, hour, dow)
        congestion_pct = scale * 50.0  # 50% baseline in _get_train_congestion_scale

        if congestion_pct <= 30:
            return 0.85
        if congestion_pct >= 100:
            return MIN_SIT_FRACTION

        t = (congestion_pct - 30) / 70
        return 0.85 - t * (0.85 - MIN_SIT_FRACTION)

    def _get_per_station_competitors(self, car_no, station, hour, direction=None, dow=None):
        """
        Estimate standing competitors for newly freed seats in car c at station s.

        Combines train-level absolute crowding with station/hour-specific
        per-car congestion distribution when available.

        DOW correction: Weekends have fewer passengers overall, so competitor
        count is scaled by the same dow_factor used for alighting volume.
        This ensures consistency — fewer alighters AND fewer competitors on weekends.
        """
        scale = self._get_train_congestion_scale(station, hour, dow)
        congestion_pct = scale * 50.0
        total_pax_per_car = (congestion_pct / 100.0) * self.MAX_CAPACITY

        # Apply DOW factor to total passengers (weekends → fewer passengers overall)
        dow_factor = self._get_dow_factor(station, dow)
        total_pax_per_car *= dow_factor

        if self._car_congestion_cache and hour is not None:
            _, h, dk = self._resolve_sk_key(station, hour, dow)
            congestion = self._car_congestion_cache.get((station, h, dk))
            if congestion and len(congestion) == self.TOTAL_CARS:
                total = sum(congestion)
                if total > 0:
                    car_fraction = congestion[car_no - 1] / total
                    pax_in_car = total_pax_per_car * self.TOTAL_CARS * car_fraction
                    standing = max(0.0, pax_in_car - self.SEATS_PER_CAR)
                    return max(0.5, standing)

        car_fraction = self.EMPIRICAL_CAR_DIST[car_no - 1]
        pax_in_car = total_pax_per_car * self.TOTAL_CARS * car_fraction
        standing = max(0.0, pax_in_car - self.SEATS_PER_CAR)
        return max(0.5, standing)

    def _get_load_factors(self, intermediates, direction, hour, dow=None):
        """
        L(c): per-car relative load factor (competition coefficient).

        Represents how crowded car c is relative to average.
        L(c) > 1 → more crowded → harder to get a freed seat.
        L(c) < 1 → less crowded → easier to get a freed seat.

        Raw L values are clamped to [0.3, 3.0] to prevent extreme outliers,
        then dampened via GAMMA: L_eff = L^GAMMA (in compute_seatscore).

        As of 2025, SK API car_congestion data is 100% complete for weekdays.
        Direct lookup across intermediate stations should always succeed for MON.

        Priority:
        1. SK API congestionCar - direct lookup (complete for weekday hours)
        2. Average w(c,s) across intermediate stations (facility-based proxy)
        3. Uniform (1.0 for all cars)
        """
        L_MIN, L_MAX = 0.3, 3.0
        loads = [0.0] * self.TOTAL_CARS
        _, _, dk = self._resolve_sk_key("", hour, dow)

        # SK API car congestion: average across intermediate stations
        # With complete data, all stations should have exact matches for weekdays
        if self._car_congestion_cache and hour is not None:
            sk_count = 0
            for s in intermediates:
                congestion = self._car_congestion_cache.get((s, hour, dk))
                if congestion and len(congestion) == self.TOTAL_CARS:
                    for i in range(self.TOTAL_CARS):
                        loads[i] += congestion[i]
                    sk_count += 1

            if sk_count > 0:
                loads = [v / sk_count for v in loads]
                mean_load = sum(loads) / self.TOTAL_CARS
                if mean_load > 0:
                    return [max(L_MIN, min(L_MAX, v / mean_load)) for v in loads]

        # Fallback: average facility-based w(c,s) across intermediate stations
        # (only reached for non-weekday dow or missing cache)
        if intermediates:
            for s in intermediates:
                for c in range(self.TOTAL_CARS):
                    loads[c] += self._get_car_weight(s, c + 1, direction, hour, dow)

            mean_load = sum(loads) / self.TOTAL_CARS
            if mean_load > 0:
                return [max(L_MIN, min(L_MAX, v / mean_load)) for v in loads]

        # Uniform fallback
        return [1.0] * self.TOTAL_CARS

    def _estimate_seat_time_for_car(self, car_no, boarding, intermediates,
                                     destination, direction, hour, dow=None,
                                     load_factors_raw=None):
        """
        Estimate expected minutes until getting a seat for car c.

        Walks through intermediate stations, accumulating expected alighting.
        When cumulative alighting suggests a seat is likely available,
        returns the travel time from boarding to that station.

        The threshold adapts to the car's load factor: less crowded cars
        (lower L) need less cumulative alighting to free a seat.
        """
        if not intermediates:
            return 0.0

        # Accumulate expected alighting per station for this car
        station_data = []
        total_alighting = 0.0
        for s in intermediates:
            D = self._get_alighting_volume(s, hour, direction, dow)
            w = self._get_car_weight(s, car_no, direction, hour, dow)
            alighting = D * w
            station_data.append((s, alighting))
            total_alighting += alighting

        if total_alighting <= 0:
            return None

        # Less crowded cars (lower L) need less cumulative alighting to free a seat
        L = load_factors_raw[car_no - 1] if load_factors_raw else 1.0
        threshold_pct = min(0.50, max(0.15, 0.30 * L))
        threshold = total_alighting * threshold_pct

        cumulative = 0.0
        for s, alighting in station_data:
            cumulative += alighting
            if cumulative >= threshold:
                travel_min = self._get_travel_time(boarding, s, direction)
                return round(travel_min, 1)

        return round(self._get_travel_time(boarding, destination, direction), 1)

    # ----- public API --------------------------------------------------------

    def compute_seatscore(self, boarding, destination, hour, direction, dow=None):
        """
        Compute SeatScore for each car.

        Returns pd.DataFrame with columns: car, benefit, penalty, score_raw, score, rank
        Also includes station_contributions for explanation UI.

        Args:
            dow: Day of week code (MON/TUE/WED/THU/FRI/SAT/SUN).
                 Adjusts D(s) using exit traffic patterns.
        """
        params = self.params
        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour, params=params)
        # 날씨 보정: 비/눈 시 지하철 혼잡도 상승 반영
        if self._weather_service:
            weather_factor = self._weather_service.get_weather_factor()
            alpha = round(alpha * weather_factor, 2)
        epsilon = 0.5

        station_context = {}
        station_load_accum = [0.0] * self.TOTAL_CARS

        for s in intermediates:
            d_alight = self._get_alighting_volume(s, hour, direction, dow)
            t_to_dest = self._get_travel_time(s, destination, direction)
            p_sit = self._get_sitting_fraction(s, hour, direction, dow)

            competitors = [
                self._get_per_station_competitors(c, s, hour, direction, dow)
                for c in range(1, self.TOTAL_CARS + 1)
            ]

            mean_comp = sum(competitors) / self.TOTAL_CARS if competitors else 1.0
            mean_comp = max(mean_comp, 1e-9)
            load_ratios = [comp / mean_comp for comp in competitors]

            for i, ratio in enumerate(load_ratios):
                station_load_accum[i] += ratio

            station_context[s] = {
                "D": d_alight,
                "T": t_to_dest,
                "p_sit": p_sit,
                "competitors": competitors,
                "load_ratios": load_ratios,
            }

        if intermediates:
            load_factors_raw = [
                station_load_accum[i] / len(intermediates)
                for i in range(self.TOTAL_CARS)
            ]
        else:
            load_factors_raw = [1.0] * self.TOTAL_CARS

        # ── GAMMA: 경쟁계수 압축 ──────────────────────────────────
        # GAMMA < 1 → load factor 분포를 압축하여 극단적 차이를 완화
        # L_eff = L^GAMMA (0.5 → sqrt, 분포가 중앙으로 모임)
        load_factors_effective = [
            max(0.01, lf) ** params.gamma for lf in load_factors_raw
        ]
        # 재정규화: 평균 1.0 유지
        lf_mean = sum(load_factors_effective) / self.TOTAL_CARS
        if lf_mean > 0:
            load_factors_effective = [lf / lf_mean for lf in load_factors_effective]
        else:
            # Fallback: if all load factors collapsed to zero, treat all cars equally
            load_factors_effective = [1.0] * self.TOTAL_CARS

        score_raw = {}
        penalties = {}
        p_seated = {}
        station_contributions = {}

        for c in range(1, self.TOTAL_CARS + 1):
            benefit = 0.0
            contributions = []

            # ── DELTA: 초기 착석 가능성 보너스 ────────────────────
            # 덜 붐비는 칸(양 끝칸)은 탑승 시점에 빈 좌석이 있을 확률이 높음
            # L_eff < 1 → 보너스 양수, L_eff > 1 → 보너스 0에 가까움
            L_eff = load_factors_effective[c - 1]
            initial_bonus = params.delta * max(0.0, 1.0 - L_eff)

            # ── 시간대 기반 초기 착석 확률 ────────────────────────
            # alpha < 1 → 한산한 시간대(심야/이른 아침): 열차가 전반적으로
            # 비어있어 탑승 시점에 이미 빈 좌석이 있을 확률이 높음.
            # alpha >= 1 → 혼잡 시간대: 탑승 시점 빈 좌석 기대 불가.
            # L_eff가 낮은 칸(양 끝)은 추가로 초기 착석 확률이 높아짐.
            if alpha < 1.0:
                base_initial_seat = (1.0 - alpha) * 0.7  # 심야(0.6) → 0.28, 이른아침(0.5) → 0.35
                car_factor = max(0.5, 1.0 - 0.5 * max(0.0, L_eff - 1.0))  # 혼잡한 칸은 감소
                p_initial_seated = min(0.6, base_initial_seat * car_factor)
            else:
                p_initial_seated = 0.0
            p_not_seated_yet = 1.0 - p_initial_seated

            # ── Competitor turnover tracking ──────────────────────
            # As the train progresses, competitors who got seats at earlier
            # stations are no longer competing. We track a decay multiplier
            # that reduces the effective competitor count at each station.
            competitor_remaining_frac = 1.0  # fraction of original competitors still standing

            for s in intermediates:
                ctx = station_context[s]
                d_alight = ctx["D"]
                t_to_dest = ctx["T"]
                p_sit = ctx["p_sit"]
                c_comp_base = ctx["competitors"][c - 1]
                l_ratio = ctx["load_ratios"][c - 1]

                w = self._get_car_weight(s, c, direction, hour, dow)
                a_freed = d_alight * w * p_sit * alpha

                # Apply competitor turnover: reduce competitors by those who
                # already sat down at previous stations
                c_comp = c_comp_base * competitor_remaining_frac

                # GAMMA 적용: 경쟁자 수를 effective load factor로 보정
                c_comp_adj = c_comp * L_eff

                # Clamp exponent to [-20, 0] to prevent underflow/overflow
                exponent = -a_freed / (epsilon + c_comp_adj)
                exponent = max(-20.0, min(0.0, exponent))
                p_capture = 1.0 - np.exp(exponent)
                p_capture = float(np.clip(p_capture, 0.0, 1.0))

                # Update competitor turnover: seats freed at this station
                # reduce the pool of standing competitors for future stations.
                # seats_freed ≈ a_freed seats become available; competitors
                # who grab them leave the standing pool.
                if c_comp > 0:
                    seats_taken_by_others = a_freed * (c_comp_adj / (epsilon + c_comp_adj))
                    frac_seated = min(0.5, seats_taken_by_others / max(1.0, c_comp))
                    competitor_remaining_frac *= (1.0 - frac_seated)

                p_first = p_capture * p_not_seated_yet
                seated_time = p_first * t_to_dest
                benefit += seated_time
                p_not_seated_yet *= (1.0 - p_capture)

                contributions.append({
                    "station": s,
                    "D": round(d_alight, 2),
                    "T": round(t_to_dest, 2),
                    "w": round(w, 4),
                    "L": round(l_ratio, 4),
                    "L_eff": round(L_eff, 4),
                    "p_sit": round(p_sit, 4),
                    "A": round(a_freed, 4),
                    "C": round(c_comp, 4),
                    "C_adj": round(c_comp_adj, 4),
                    "p_capture": round(p_capture, 6),
                    "p_first": round(p_first, 6),
                    "contribution": round(seated_time, 4),
                })

            # DELTA 보너스를 최종 benefit에 가산
            # 총 이동시간 비례로 스케일링하여 경로 길이에 무관하게 동작
            total_trip = self._get_travel_time(boarding, destination, direction)
            benefit += initial_bonus * total_trip

            # ── PENALTY (β·B): 탑승 혼잡도 패널티 ────────────────
            # B(c,h): 탑승역에서의 칸별 혼잡도 비율 (SK API car_congestion 기반)
            # 혼잡한 칸일수록 패널티가 커짐 → benefit에서 차감
            # total_trip 스케일링으로 benefit과 동일한 단위(분) 유지
            penalty_raw = self._get_boarding_penalty(c, boarding, hour, direction, dow)
            penalty_val = params.beta * penalty_raw * total_trip

            score_raw[c] = benefit - penalty_val
            penalties[c] = round(penalty_val, 4)
            p_seated[c] = float(np.clip(1.0 - p_not_seated_yet, 0.0, 0.95))
            station_contributions[c] = contributions

        result = pd.DataFrame([
            {
                "car": c,
                "benefit": score_raw[c] + penalties[c],  # original benefit before penalty
                "penalty": penalties[c],
                "load_factor": round(load_factors_raw[c - 1], 4),
                "load_factor_eff": round(load_factors_effective[c - 1], 4),
                "score_raw": score_raw[c],
            }
            for c in range(1, self.TOTAL_CARS + 1)
        ])

        scores_raw = np.asarray(result["score_raw"].to_numpy(dtype=float), dtype=float)
        score_max = float(np.max(scores_raw))
        score_min = float(np.min(scores_raw))
        if score_max > score_min:
            normalized = (scores_raw - score_min) / (score_max - score_min)
            # Adaptive sigmoid: steepness adjusts based on raw score spread
            # Small spread (< 1 min difference) → gentle sigmoid (3.0) for visible differentiation
            # Large spread (> 5 min) → steeper sigmoid (5.0) to compress outliers
            # Default: 4.0 (softer than previous 6.0, better score distribution)
            raw_spread = score_max - score_min
            if raw_spread < 1.0:
                steepness = 3.0
            elif raw_spread > 5.0:
                steepness = 5.0
            else:
                steepness = 4.0
            stretched = 1.0 / (1.0 + np.exp(-steepness * (normalized - 0.5)))
            result["score"] = np.clip(5 + stretched * 90, 5, 95)
        else:
            # All cars have identical raw scores (e.g., adjacent stations, no data).
            # Use load_factors as tiebreaker: less crowded cars get slightly higher scores.
            lf_arr = np.array(load_factors_raw)
            lf_spread = float(np.max(lf_arr) - np.min(lf_arr))
            if lf_spread > 1e-9:
                lf_norm = (lf_arr - np.min(lf_arr)) / lf_spread  # 0-1
                result["score"] = 50.0 - lf_norm * 5.0  # less crowded = higher (47.5-52.5)
            else:
                result["score"] = 50.0

        result = result.sort_values("score", ascending=False)
        result["rank"] = range(1, len(result) + 1)

        # gap between 1st and last
        result["gap_from_best"] = result["score"].max() - result["score"]
        # spread metric
        result["spread"] = result["score"].max() - result["score"].min()

        # Attach station contributions metadata
        result.attrs["station_contributions"] = station_contributions
        result.attrs["load_factors_raw"] = load_factors_raw
        result.attrs["p_seated"] = p_seated

        return result.reset_index(drop=True)

    def recommend(self, boarding_station, destination_station, hour, direction="내선", dow=None):
        boarding = normalize_station_name(boarding_station)
        destination = normalize_station_name(destination_station)

        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour)
        weather_factor = None
        # 날씨 보정: 비/눈 시 지하철 혼잡도 상승 반영
        if self._weather_service:
            weather_factor = self._weather_service.get_weather_factor()
            alpha = round(alpha * weather_factor, 2)
        scores_df = self.compute_seatscore(boarding, destination, hour, direction, dow)

        best = scores_df.iloc[0]
        worst = scores_df.iloc[-1]

        # Get station contributions for explanation
        station_contribs = scores_df.attrs.get("station_contributions", {})
        p_seated = scores_df.attrs.get(
            "p_seated",
            {c: 0.0 for c in range(1, self.TOTAL_CARS + 1)},
        )

        # Get boarding station congestion for context
        boarding_congestion = None
        if self._congestion_30min_cache:
            dir_key = "내선" if ("내선" in str(direction) or "하행" in str(direction)) else "외선"
            boarding_congestion = self._congestion_30min_cache.get(
                (boarding, dir_key, hour)
            )

        # Extract load factors from scores_df
        load_factors_map = {
            int(row["car"]): row["load_factor"]
            for _, row in scores_df.iterrows()
        }

        # Build per-query data quality report
        _, _, dk = self._resolve_sk_key(boarding, hour, dow)
        data_quality = {}
        # Check if SK API data was used for this specific query
        # getoff_rate: 100% complete for weekdays (817 entries, 43 stations x 19 hours)
        if self._getoff_rate_cache:
            has_exact = any(
                self._getoff_rate_cache.get((s, hour, dk)) is not None
                for s in intermediates
            )
            # With complete weekday data, exact should always be True for MON
            data_quality["getoff_rate"] = "exact" if has_exact else "fallback"
        else:
            data_quality["getoff_rate"] = "fallback"

        # car_congestion: 100% complete for weekdays (817 entries, 43 stations x 19 hours)
        if self._car_congestion_cache:
            has_exact = any(
                self._car_congestion_cache.get((s, hour, dk)) is not None
                for s in intermediates
            )
            # With complete weekday data, exact should always be True for MON
            data_quality["car_congestion"] = "exact" if has_exact else "fallback"
        else:
            data_quality["car_congestion"] = "fallback"

        if self._train_congestion_cache:
            tc = self._train_congestion_cache.get((boarding, hour, dk))
            has_interp = tc is None and self._find_nearest_rush_data(
                self._train_congestion_cache, boarding, hour, dk
            )
            data_quality["train_congestion"] = "exact" if tc is not None else ("interpolated" if has_interp else "fallback")
        else:
            data_quality["train_congestion"] = "fallback"

        data_quality["congestion_30min"] = "exact" if boarding_congestion is not None else "fallback"
        data_quality["travel_times"] = "exact" if self._tt_stations else "fallback"

        # Estimate expected time until seating using per-station capture probabilities
        seat_times = {}
        total_trip_time = self._get_travel_time(boarding, destination, direction)
        for c in range(1, self.TOTAL_CARS + 1):
            contribs = station_contribs.get(c, [])
            if not contribs:
                seat_times[c] = 0.0 if not intermediates else round(total_trip_time, 1)
                continue

            expected_wait = 0.0
            p_first_sum = 0.0
            for entry in contribs:
                p_first = float(entry.get("p_first", 0.0))
                station = entry.get("station")
                t_board = (
                    self._get_travel_time(boarding, station, direction)
                    if station else total_trip_time
                )
                expected_wait += p_first * t_board
                p_first_sum += p_first

            remaining = max(0.0, 1.0 - p_first_sum)
            expected_wait += remaining * total_trip_time
            seat_times[c] = round(expected_wait, 1)

        return {
            "boarding": boarding,
            "destination": destination,
            "hour": hour,
            "direction": direction,
            "alpha": alpha,
            "weather_factor": weather_factor,
            "n_intermediate": len(intermediates),
            "intermediates": intermediates,
            "scores": scores_df,
            "best_car": int(best["car"]),
            "best_score": best["score"],
            "worst_car": int(worst["car"]),
            "worst_score": worst["score"],
            "score_spread": best["score"] - worst["score"],
            "station_contributions": station_contribs,
            "boarding_congestion": boarding_congestion,
            "load_factors": load_factors_map,
            "p_seated": p_seated,
            "data_sources": list(self.data_sources.keys()),
            "data_quality": data_quality,
            "seat_times": seat_times,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    engine = SeatScoreEngine(
        data_dir="../data/processed",
        raw_dir="../data/raw",
    )
    engine.load_all()

    scenarios = [
        {"name": "Morning: Gangnam->City Hall", "boarding": "강남", "dest": "시청", "hour": 8, "dir": "내선"},
        {"name": "Evening: Hongdae->Gangnam", "boarding": "홍대입구", "dest": "강남", "hour": 18, "dir": "외선"},
        {"name": "Weekend: Jamsil->Sinchon", "boarding": "잠실", "dest": "신촌", "hour": 14, "dir": "내선"},
    ]

    for sc in scenarios:
        r = engine.recommend(sc["boarding"], sc["dest"], sc["hour"], sc["dir"])
        print(f"\n{'='*60}")
        print(f"{sc['name']}  (alpha={r['alpha']}, stops={r['n_intermediate']})")
        print(f"Data sources: {r['data_sources']}")
        if r['boarding_congestion']:
            print(f"Boarding congestion: {r['boarding_congestion']:.1f}%")
        print(f"{'='*60}")
        for _, row in r["scores"].iterrows():
            bar = "#" * int(row["score"] / 5)
            L = row["load_factor"]
            print(f"  Car {int(row['car']):>2} | {row['score']:5.1f} | L={L:.2f} | gap -{row['gap_from_best']:4.1f} | {bar}")
        print(f"  Best: Car {r['best_car']}  Worst: Car {r['worst_car']}  "
              f"Spread: {r['score_spread']:.1f}")
        print(f"  Load factors: " + ", ".join(
            f"C{k}={v:.2f}" for k, v in sorted(r['load_factors'].items())
        ))
