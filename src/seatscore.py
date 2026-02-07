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

    def _get_alighting_volume(self, station, hour, direction=None):
        """
        D(s): alighting volume at station s during hour h.

        Priority:
        1. Direction-aware 30-min congestion data (if available)
        2. Hourly alighting cache (backward compatible)
        3. Fallback: 1.0
        """
        # Try direction-aware 30-min data first
        if self._congestion_30min_cache and direction:
            dir_key = "내선" if ("내선" in str(direction) or "하행" in str(direction)) else "외선"
            val = self._congestion_30min_cache.get((station, dir_key, hour))
            if val is not None:
                return val

            # Try without direction specificity
            for key, v in self._congestion_30min_cache.items():
                if key[0] == station and key[2] == hour:
                    return v

        # Fallback to hourly cache
        return self._alighting_cache.get((station, hour), 1.0)

    def _get_travel_time(self, station_from, station_to):
        """T(s->dest): remaining travel time proxy (km-based)."""
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

    def _get_car_weight(self, station, car_no, direction, hour=None):
        """
        w(c,s): per-car alighting weight at station s.

        Priority:
        1. SK API getOffCarRate (real measurement)
        2. Facility-based estimation (fast exit data)
        3. Uniform distribution (1/10)
        """
        # Try SK API getoff rate
        if self._getoff_rate_cache and hour is not None:
            # Try weekday first
            rates = self._getoff_rate_cache.get((station, hour, "MON"))
            if rates and len(rates) == self.TOTAL_CARS:
                total = sum(rates)
                if total > 0:
                    return rates[car_no - 1] / total
                return 1.0 / self.TOTAL_CARS

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

    def _get_boarding_penalty(self, car_no, boarding_station, hour, direction):
        """
        B(c,h): boarding congestion penalty per car.

        Priority:
        1. SK API congestionCar (real per-car congestion)
        2. Facility-based estimation
        """
        # Try SK API car congestion
        if self._car_congestion_cache and hour is not None:
            congestion = self._car_congestion_cache.get((boarding_station, hour, "MON"))
            if congestion and len(congestion) == self.TOTAL_CARS:
                total = sum(congestion)
                if total > 0:
                    return congestion[car_no - 1] / total
                return 1.0 / self.TOTAL_CARS

        # Fallback to facility-based penalty
        return self._get_facility_score(boarding_station, car_no, direction)

    # ----- public API --------------------------------------------------------

    def compute_seatscore(self, boarding, destination, hour, direction):
        """
        Compute SeatScore for each car.

        Returns pd.DataFrame with columns: car, benefit, penalty, score_raw, score, rank
        Also includes station_contributions for explanation UI.
        """
        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour)

        # compute raw scores with per-station contribution tracking
        raw_scores = {}
        station_contributions = {}  # {car: [{station, D, T, w, contribution}, ...]}

        for c in range(1, self.TOTAL_CARS + 1):
            benefit = 0.0
            contributions = []
            for s in intermediates:
                D = self._get_alighting_volume(s, hour, direction)
                T = self._get_travel_time(s, destination)
                w = self._get_car_weight(s, c, direction, hour)
                contrib = D * T * w * alpha
                benefit += contrib
                contributions.append({
                    "station": s,
                    "D": round(D, 2),
                    "T": round(T, 2),
                    "w": round(w, 4),
                    "contribution": round(contrib, 2),
                })
            raw_scores[c] = benefit
            station_contributions[c] = contributions

        # boarding penalty scaled by average alighting volume
        avg_D = np.mean([
            self._get_alighting_volume(s, hour, direction)
            for s in intermediates
        ]) if intermediates else 1.0

        boarding_penalty = {}
        for c in range(1, self.TOTAL_CARS + 1):
            B = self._get_boarding_penalty(c, boarding, hour, direction)
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

    def recommend(self, boarding_station, destination_station, hour, direction="내선"):
        boarding = normalize_station_name(boarding_station)
        destination = normalize_station_name(destination_station)

        intermediates = self._get_intermediate_stations(boarding, destination, direction)
        alpha = self._get_alpha(hour)
        scores_df = self.compute_seatscore(boarding, destination, hour, direction)

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
            "data_sources": list(self.data_sources.keys()),
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
            print(f"  Car {int(row['car']):>2} | {row['score']:5.1f} | gap -{row['gap_from_best']:4.1f} | {bar}")
        print(f"  Best: Car {r['best_car']}  Worst: Car {r['worst_car']}  "
              f"Spread: {r['score_spread']:.1f}")
