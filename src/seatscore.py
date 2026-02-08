# -*- coding: utf-8 -*-
"""
SeatScore Decision Model v3
============================
Utility-based decision model for per-car seating recommendation.

Formula:
    SeatScore(c) = sum_s [ D(s) * T(s->dest) * w(c,s) * alpha(h) ] - beta * B(c,h)

Components:
    D(s)          : alighting volume at intermediate station s
                    Source: 서울교통공사 혼잡도 (30-min, direction-aware)
    T(s->dest)    : remaining travel time from s to destination (seat-time benefit)
    w(c,s)        : per-car alighting distribution at station s
                    Source: SK API getOffCarRate (fallback: fast-exit facility weight)
    alpha(h)      : time-of-day congestion multiplier (rush vs off-peak)
                    Source: calibrated from real congestion data
    B(c,h)        : boarding congestion penalty per car
                    Source: SK API congestionCar (fallback: facility weight)
    beta          : penalty coefficient balancing exit benefit vs boarding cost

v3 improvements over v2:
    - 30-min granularity congestion data (5 quarterly files, 2024-2025)
    - Direction-aware congestion (내선/외선 separate)
    - SK API data hooks (car congestion, alighting rates, train congestion)
    - Per-station contribution data for explanation UI
    - Day-type awareness (weekday/weekend)
    - Graceful fallback: SK API data → facility data → uniform
"""

import json
import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_station_name(name):
    if pd.isna(name):
        return ""
    name = str(name)
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"역$", "", name)       # 접미사 "역"만 제거 (역삼 등 보존)
    name = name.replace(" ", "").strip()
    return name


# ---------------------------------------------------------------------------
# SeatScore Engine v3
# ---------------------------------------------------------------------------

class SeatScoreEngine:
    """
    Compute per-car seating utility scores for a given trip on Line 2.

    v3 data sources:
    - 서울교통공사 혼잡도 30-min data (congestion_30min.csv)
    - Seoul Fast Exit API data (fast_exit_line2.json)
    - SK Open API car-level data (when available)
    - Interstation distance data

    Graceful degradation: works with any subset of data available.
    """

    TOTAL_CARS = 10  # Line 2 uses 10-car trains

    # Facility type weights: escalator/elevator > stairs
    FACILITY_WEIGHTS = {
        "에스컬레이터": 1.5,
        "엘리베이터":   1.2,
        "계단":         1.0,
    }

    # Time-of-day congestion multiplier
    ALPHA_MAP = {
        "morning_rush": 1.4,   # 07-09
        "evening_rush":  1.3,   # 18-20
        "midday":        1.0,   # 10-17
        "evening":       0.9,   # 20-22
        "night":         0.6,   # 22-06
        "early":         0.5,   # 04-07
    }

    # Penalty coefficient for boarding crowding
    BETA = 0.3

    # Competition factor strength: how much L(c) affects scores
    # 0.0 = no effect (original behavior), 1.0 = full effect
    GAMMA = 0.5

    def __init__(self, data_dir="data_processed", raw_dir="data_raw"):
        self.data_dir = Path(data_dir)
        self.raw_dir = Path(raw_dir)

        self.fast_exit_df = None
        self.congestion_df = None
        self.distance_df = None
        self.station_order = []

        # precomputed caches
        self._facility_cache = {}
        self._station_dir_total = {}
        self._alighting_cache = {}
        self._congestion_30min_cache = {}   # (station, direction, hour) → congestion %
        self._car_congestion_cache = None   # SK API: (station, hour, dow) → [10 values]
        self._getoff_rate_cache = None      # SK API: (station, hour, dow) → [10 values]
        self._train_congestion_cache = None # SK API: (station, hour, dow) → value
        self._travel_time_matrix = None     # TMAP: station→station → seconds
        self._exit_traffic_cache = {}       # exit traffic: (station, dow) → {exit_no: count}

        # data source tracking
        self.data_sources = {}

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
        print(f"SeatScoreEngine v3: all data loaded.")
        print(f"  Data sources: {self.data_sources}")

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
                with open(pkl_path, "rb") as f:
                    self._alighting_cache = pickle.load(f)
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
        Precompute per (station, direction, car) facility score.

        Score = sum of facility weights for each exit record.
        """
        if self.fast_exit_df is None:
            return

        df = self.fast_exit_df.copy()

        # map facility names to weights
        df["fac_weight"] = df["plfmCmgFac"].map(self.FACILITY_WEIGHTS).fillna(1.0)

        grouped = df.groupby(
            ["station_normalized", "upbdnbSe", "car_no"]
        )["fac_weight"].sum()

        self._facility_cache = grouped.to_dict()

        # also compute per-station-direction total for normalization
        self._station_dir_total = df.groupby(
            ["station_normalized", "upbdnbSe"]
        )["fac_weight"].sum().to_dict()

        self.data_sources["facility_cache"] = len(self._facility_cache)
        print(f"  Facility cache: {len(self._facility_cache)} entries")

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
                with open(pkl_path, "rb") as f:
                    cache = pickle.load(f)
                setattr(self, attr, cache)
                self.data_sources[f"sk_{filename}"] = len(cache)
                print(f"  SK {filename}: {len(cache)} entries")
            else:
                print(f"  SK {filename}: not found (using fallback)")

    def _load_travel_times(self):
        """Load TMAP transit cumulative travel times if available."""
        cum_path = self.data_dir / "cumulative_times.pkl"
        if cum_path.exists():
            with open(cum_path, "rb") as f:
                cum_data = pickle.load(f)
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
            with open(pkl_path, "rb") as f:
                self._exit_traffic_cache = pickle.load(f)
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

    def _get_alpha(self, hour):
        """
        Time-of-day congestion multiplier using smooth interpolation.

        Uses a continuous function instead of discrete buckets for smoother
        transitions between time periods. Peak at 8am (morning rush) and
        6:30pm (evening rush), with gradual decay towards night hours.
        """
        anchors = [
            (0, 0.6),    # midnight - low
            (4, 0.5),    # early morning - very low
            (6, 0.7),    # starting to pick up
            (7, 1.1),    # building to morning rush
            (8, 1.4),    # morning rush peak
            (9, 1.2),    # post-rush
            (10, 1.0),   # midday start
            (12, 1.0),   # lunch
            (14, 1.0),   # afternoon
            (17, 1.1),   # building to evening rush
            (18, 1.3),   # evening rush starts
            (19, 1.35),  # evening rush peak
            (20, 1.1),   # post-rush
            (21, 0.9),   # evening
            (22, 0.7),   # late evening
            (23, 0.6),   # night
            (24, 0.6),   # wrap to midnight
        ]

        h = hour % 24

        for i in range(len(anchors) - 1):
            h1, a1 = anchors[i]
            h2, a2 = anchors[i + 1]
            if h1 <= h < h2:
                ratio = (h - h1) / (h2 - h1)
                return round(a1 + ratio * (a2 - a1), 2)

        return self.ALPHA_MAP.get("midday", 1.0)

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

        Priority:
        1. SK API getOffCarRate (real measurement, dow-aware)
        2. Nearest rush hour interpolation
        3. Facility-based estimation (fast exit data)
        4. Uniform distribution (1/10)
        """
        # Try SK API getoff rate
        if self._getoff_rate_cache and hour is not None:
            _, h, dk = self._resolve_sk_key(station, hour, dow)
            rates = self._getoff_rate_cache.get((station, h, dk))
            if rates and len(rates) == self.TOTAL_CARS:
                total = sum(rates)
                if total > 0:
                    return rates[car_no - 1] / total
                return 1.0 / self.TOTAL_CARS

            # Try nearest rush hour interpolation
            result = self._find_nearest_rush_data(
                self._getoff_rate_cache, station, hour, dk
            )
            if result:
                data, decay = result
                if len(data) == self.TOTAL_CARS:
                    total = sum(data)
                    if total > 0:
                        uniform = 1.0 / self.TOTAL_CARS
                        real_w = data[car_no - 1] / total
                        return decay * real_w + (1 - decay) * uniform

        # Fallback to facility-based weight
        return self._get_facility_score(station, car_no, direction)

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

        Priority:
        1. SK API congestionCar (real per-car congestion, dow-aware)
        2. Nearest rush hour interpolation
        3. Facility-based estimation

        When train_congestion data is available, it scales the penalty
        by the actual train-level crowding (higher train congestion → bigger penalty).
        """
        base_penalty = None

        # Try SK API car congestion
        if self._car_congestion_cache and hour is not None:
            _, h, dk = self._resolve_sk_key(boarding_station, hour, dow)
            congestion = self._car_congestion_cache.get((boarding_station, h, dk))
            if congestion and len(congestion) == self.TOTAL_CARS:
                total = sum(congestion)
                if total > 0:
                    base_penalty = congestion[car_no - 1] / total

            # Try nearest rush hour interpolation
            if base_penalty is None:
                result = self._find_nearest_rush_data(
                    self._car_congestion_cache, boarding_station, hour, dk
                )
                if result:
                    data, decay = result
                    if len(data) == self.TOTAL_CARS:
                        total = sum(data)
                        if total > 0:
                            uniform = 1.0 / self.TOTAL_CARS
                            real_p = data[car_no - 1] / total
                            base_penalty = decay * real_p + (1 - decay) * uniform

        if base_penalty is None:
            base_penalty = self._get_facility_score(boarding_station, car_no, direction)

        # Scale by train-level congestion if available
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

    def _get_load_factors(self, intermediates, direction, hour, dow=None):
        """
        L(c): per-car relative load factor (competition coefficient).

        Represents how crowded car c is relative to average.
        L(c) > 1 → more crowded → harder to get a freed seat.
        L(c) < 1 → less crowded → easier to get a freed seat.

        Raw L values are clamped to [0.3, 3.0] to prevent extreme outliers,
        then dampened via GAMMA: L_eff = L^GAMMA (in compute_seatscore).

        Priority:
        1. SK API congestionCar (real per-car crowding, dow-aware + rush interpolation)
        2. Average w(c,s) across intermediate stations (facility-based proxy)
        3. Uniform (1.0 for all cars)
        """
        L_MIN, L_MAX = 0.3, 3.0
        loads = [0.0] * self.TOTAL_CARS
        _, _, dk = self._resolve_sk_key("", hour, dow)

        # Try SK API car congestion: average across intermediate stations
        if self._car_congestion_cache and hour is not None:
            sk_count = 0
            for s in intermediates:
                congestion = self._car_congestion_cache.get((s, hour, dk))
                if congestion and len(congestion) == self.TOTAL_CARS:
                    for i in range(self.TOTAL_CARS):
                        loads[i] += congestion[i]
                    sk_count += 1
                else:
                    # Try nearest rush hour interpolation
                    result = self._find_nearest_rush_data(
                        self._car_congestion_cache, s, hour, dk
                    )
                    if result:
                        data, decay = result
                        if len(data) == self.TOTAL_CARS:
                            uniform_val = sum(data) / self.TOTAL_CARS
                            for i in range(self.TOTAL_CARS):
                                loads[i] += decay * data[i] + (1 - decay) * uniform_val
                            sk_count += 1

            if sk_count > 0:
                loads = [v / sk_count for v in loads]
                mean_load = sum(loads) / self.TOTAL_CARS
                if mean_load > 0:
                    return [max(L_MIN, min(L_MAX, v / mean_load)) for v in loads]

        # Fallback: average facility-based w(c,s) across intermediate stations
        if intermediates:
            for s in intermediates:
                for c in range(self.TOTAL_CARS):
                    loads[c] += self._get_car_weight(s, c + 1, direction, hour, dow)

            mean_load = sum(loads) / self.TOTAL_CARS
            if mean_load > 0:
                return [max(L_MIN, min(L_MAX, v / mean_load)) for v in loads]

        # Uniform fallback
        return [1.0] * self.TOTAL_CARS

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
        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour)

        # Weekend alpha adjustment: reduce by ~15% on weekends
        if dow in ("SAT", "SUN"):
            alpha = round(alpha * 0.85, 2)

        # competition factor: relative per-car crowding
        load_factors_raw = self._get_load_factors(intermediates, direction, hour, dow)
        # Apply GAMMA dampening: L_eff = L^GAMMA
        # GAMMA=0 → no effect, GAMMA=1 → full effect, GAMMA=0.5 → sqrt dampening
        load_factors = [L ** self.GAMMA for L in load_factors_raw]

        # compute raw scores with per-station contribution tracking
        raw_scores = {}
        station_contributions = {}  # {car: [{station, D, T, w, contribution}, ...]}

        for c in range(1, self.TOTAL_CARS + 1):
            L = load_factors[c - 1]
            benefit = 0.0
            contributions = []
            for s in intermediates:
                D = self._get_alighting_volume(s, hour, direction, dow)
                T = self._get_travel_time(s, destination, direction)
                w = self._get_car_weight(s, c, direction, hour, dow)
                contrib = D * T * w * alpha / L if L > 0 else 0.0
                benefit += contrib
                contributions.append({
                    "station": s,
                    "D": round(D, 2),
                    "T": round(T, 2),
                    "w": round(w, 4),
                    "L": round(L, 4),
                    "contribution": round(contrib, 2),
                })
            raw_scores[c] = benefit
            station_contributions[c] = contributions

        # boarding penalty scaled by average alighting volume
        avg_D = np.mean([
            self._get_alighting_volume(s, hour, direction, dow)
            for s in intermediates
        ]) if intermediates else 1.0

        boarding_penalty = {}
        for c in range(1, self.TOTAL_CARS + 1):
            B = self._get_boarding_penalty(c, boarding, hour, direction, dow)
            boarding_penalty[c] = self.BETA * B * avg_D * len(intermediates)

        # final score = benefit - penalty
        final_scores = {
            c: raw_scores[c] - boarding_penalty[c]
            for c in range(1, self.TOTAL_CARS + 1)
        }

        result = pd.DataFrame([
            {
                "car": c,
                "benefit": raw_scores[c],
                "penalty": boarding_penalty[c],
                "load_factor": round(load_factors[c - 1], 4),
                "score_raw": final_scores[c],
            }
            for c in range(1, self.TOTAL_CARS + 1)
        ])

        # Z-score normalization
        scores = result["score_raw"].values
        mean_score = scores.mean()

        if mean_score > 0 and scores.std() > 0:
            z = (scores - mean_score) / scores.std()
            result["score"] = np.clip(50 + z * 15, 5, 95)
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

        return result.reset_index(drop=True)

    def recommend(self, boarding_station, destination_station, hour, direction="내선", dow=None):
        boarding = normalize_station_name(boarding_station)
        destination = normalize_station_name(destination_station)

        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour)
        if dow in ("SAT", "SUN"):
            alpha = round(alpha * 0.85, 2)
        scores_df = self.compute_seatscore(boarding, destination, hour, direction, dow)

        best = scores_df.iloc[0]
        worst = scores_df.iloc[-1]

        # Get station contributions for explanation
        station_contribs = scores_df.attrs.get("station_contributions", {})

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
        if self._getoff_rate_cache:
            has_exact = any(
                self._getoff_rate_cache.get((s, hour, dk)) is not None
                for s in intermediates
            )
            has_interp = not has_exact and any(
                self._find_nearest_rush_data(self._getoff_rate_cache, s, hour, dk)
                for s in intermediates
            )
            data_quality["getoff_rate"] = "exact" if has_exact else ("interpolated" if has_interp else "fallback")
        else:
            data_quality["getoff_rate"] = "fallback"

        if self._car_congestion_cache:
            has_exact = any(
                self._car_congestion_cache.get((s, hour, dk)) is not None
                for s in intermediates
            )
            has_interp = not has_exact and any(
                self._find_nearest_rush_data(self._car_congestion_cache, s, hour, dk)
                for s in intermediates
            )
            data_quality["car_congestion"] = "exact" if has_exact else ("interpolated" if has_interp else "fallback")
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

        return {
            "boarding": boarding,
            "destination": destination,
            "hour": hour,
            "direction": direction,
            "alpha": alpha,
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
            "data_sources": list(self.data_sources.keys()),
            "data_quality": data_quality,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    engine = SeatScoreEngine(
        data_dir="../data_processed",
        raw_dir="../data_raw",
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
