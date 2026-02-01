"""
Process New Congestion Data Files (서울교통공사 열차혼잡도)
=========================================================
Processes 5 quarterly/semi-annual congestion data files with 30-minute
granularity into an updated alighting/boarding cache for SeatScore.

Input files:
  - 서울교통공사_지하철혼잡도정보_20240630.csv (H1 2024)
  - 서울교통공사_지하철혼잡도정보_20241231.csv (H2 2024)
  - 서울교통공사_지하철혼잡도정보_20250331.xlsx (Q1 2025)
  - 서울교통공사_열차혼잡도(2025년 3분기).xlsx (Q3 2025)
  - 서울교통공사_열차혼잡도(25년4분기).xlsx (Q4 2025)

Output:
  - data_processed/congestion_30min.csv (long format, 30-min intervals)
  - data_processed/congestion_long.csv (updated hourly, backward compatible)
  - data_processed/alighting_cache.pkl (updated cache for SeatScore)
"""

import pandas as pd
import numpy as np
import pickle
import re
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def normalize_station_name(name):
    """Normalize station name for consistent matching."""
    if pd.isna(name):
        return ""
    name = str(name).strip()
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"역$", "", name)
    name = name.replace(" ", "").strip()
    return name


def parse_time_column(col_name):
    """
    Parse various time column formats into (hour, minute) tuple.

    Handles:
      - '5시30분' -> (5, 30)
      - '05:30~06:00' -> (5, 30)
      - '5시30분~6시00분' -> (5, 30)
    """
    col_name = str(col_name).strip()

    # Format: '05:30~06:00'
    m = re.match(r"(\d{1,2}):(\d{2})~", col_name)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Format: '5시30분' or '5시30분~6시00분'
    m = re.match(r"(\d{1,2})시(\d{1,2})분", col_name)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None


def load_csv_file(filepath):
    """Load CSV with encoding auto-detection."""
    for enc in ["cp949", "utf-8-sig", "utf-8", "euc-kr"]:
        try:
            return pd.read_csv(filepath, encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Cannot decode: {filepath}")


def load_congestion_file(filepath, file_label=""):
    """
    Load a single congestion file and convert to long format.

    Returns DataFrame with columns:
      station, station_normalized, direction, day_type, hour, minute, congestion
    """
    filepath = Path(filepath)
    print(f"\n--- Loading: {filepath.name} ({file_label}) ---")

    if filepath.suffix == ".csv":
        df = load_csv_file(filepath)
    else:
        df = pd.read_excel(filepath)

    print(f"  Raw shape: {df.shape}")
    print(f"  Columns: {list(df.columns[:8])}...")

    # Identify metadata columns vs time columns
    # Metadata columns are non-numeric identifiers
    meta_cols = []
    time_cols = []

    for col in df.columns:
        parsed = parse_time_column(col)
        if parsed is not None:
            time_cols.append((col, parsed[0], parsed[1]))
        else:
            meta_cols.append(col)

    print(f"  Meta columns: {meta_cols}")
    print(f"  Time columns: {len(time_cols)}")

    if not time_cols:
        print("  WARNING: No time columns found!")
        return pd.DataFrame()

    # Standardize metadata column names
    col_map = {}
    for col in meta_cols:
        col_lower = col.strip()
        if col_lower in ("요일구분", "구분"):
            col_map[col] = "day_type"
        elif col_lower == "호선":
            col_map[col] = "line"
        elif col_lower == "역번호":
            col_map[col] = "station_code"
        elif col_lower in ("출발역", "역명"):
            col_map[col] = "station"
        elif col_lower == "상하구분":
            col_map[col] = "direction"
        elif col_lower == "연번":
            col_map[col] = "seq"

    df = df.rename(columns=col_map)

    # Filter Line 2 only
    if "line" in df.columns:
        line_col = df["line"].astype(str)
        line2_mask = line_col.str.contains("2")
        df = df[line2_mask].copy()
        print(f"  After Line 2 filter: {len(df)} rows")

    if len(df) == 0:
        return pd.DataFrame()

    # Clean day_type whitespace
    if "day_type" in df.columns:
        df["day_type"] = df["day_type"].str.strip()

    # Melt time columns to long format
    time_col_names = [tc[0] for tc in time_cols]

    id_vars = [c for c in df.columns if c not in time_col_names]
    df_long = df.melt(
        id_vars=id_vars,
        value_vars=time_col_names,
        var_name="time_slot",
        value_name="congestion",
    )

    # Parse hour and minute from time_slot
    df_long["hour"] = df_long["time_slot"].apply(
        lambda x: parse_time_column(x)[0] if parse_time_column(x) else None
    )
    df_long["minute"] = df_long["time_slot"].apply(
        lambda x: parse_time_column(x)[1] if parse_time_column(x) else None
    )

    # Drop rows where time parsing failed
    df_long = df_long.dropna(subset=["hour", "minute"])
    df_long["hour"] = df_long["hour"].astype(int)
    df_long["minute"] = df_long["minute"].astype(int)

    # Normalize station names
    if "station" in df_long.columns:
        df_long["station_normalized"] = df_long["station"].apply(
            normalize_station_name
        )

    # Add source label
    df_long["source"] = file_label

    # Convert congestion to numeric
    df_long["congestion"] = pd.to_numeric(df_long["congestion"], errors="coerce")

    print(f"  Long format: {len(df_long)} rows")
    print(
        f"  Stations: {df_long['station_normalized'].nunique() if 'station_normalized' in df_long.columns else 'N/A'}"
    )

    return df_long


def process_all_files(input_dir):
    """Load and combine all congestion files."""
    input_dir = Path(input_dir)

    files_config = [
        ("서울교통공사_지하철혼잡도정보_20240630 (1).csv", "H1_2024"),
        ("서울교통공사_지하철혼잡도정보_20241231 (1).csv", "H2_2024"),
        ("서울교통공사_지하철혼잡도정보_20250331 (1).xlsx", "Q1_2025"),
        ("서울교통공사_열차혼잡도(2025년 3분기).xlsx", "Q3_2025"),
        ("서울교통공사_열차혼잡도(25년4분기).xlsx", "Q4_2025"),
    ]

    all_dfs = []
    for filename, label in files_config:
        filepath = input_dir / filename
        if filepath.exists():
            df = load_congestion_file(filepath, label)
            if len(df) > 0:
                all_dfs.append(df)
        else:
            print(f"  SKIP: {filename} not found")

    if not all_dfs:
        print("ERROR: No data files loaded!")
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\n=== Combined: {len(combined)} rows ===")
    print(f"Sources: {combined['source'].value_counts().to_dict()}")

    return combined


def build_weighted_average(combined_df):
    """
    Build weighted average congestion by station/direction/day_type/time.

    More recent data gets higher weight:
      H1_2024: 0.5, H2_2024: 0.7, Q1_2025: 0.85, Q3_2025: 1.0, Q4_2025: 1.2
    """
    source_weights = {
        "H1_2024": 0.5,
        "H2_2024": 0.7,
        "Q1_2025": 0.85,
        "Q3_2025": 1.0,
        "Q4_2025": 1.2,
    }

    df = combined_df.copy()
    df["weight"] = df["source"].map(source_weights).fillna(1.0)
    df["weighted_congestion"] = df["congestion"] * df["weight"]

    group_cols = ["station_normalized", "direction", "day_type", "hour", "minute"]
    available_cols = [c for c in group_cols if c in df.columns]

    agg = (
        df.groupby(available_cols)
        .agg(
            congestion_mean=("congestion", "mean"),
            congestion_weighted=("weighted_congestion", "sum"),
            total_weight=("weight", "sum"),
            n_sources=("source", "nunique"),
        )
        .reset_index()
    )

    agg["congestion_weighted_avg"] = agg["congestion_weighted"] / agg["total_weight"]

    return agg


def build_hourly_alighting_proxy(congestion_30min):
    """
    Convert 30-min congestion data to hourly alighting estimates.

    Congestion percentage reflects how full the train is. A DROP in congestion
    from one station to the next implies net alighting. We use the congestion
    level as a proxy for station activity.

    For backward compatibility with the existing SeatScore engine, we produce
    (station_normalized, hour) → estimated alighting volume.
    """
    df = congestion_30min.copy()

    # Filter to weekday (평일) as primary for commuting
    if "day_type" in df.columns:
        weekday = df[df["day_type"] == "평일"]
        if len(weekday) > 0:
            df = weekday

    # Average across 30-min slots within each hour
    group_cols = ["station_normalized", "direction", "hour"]
    available = [c for c in group_cols if c in df.columns]

    hourly = (
        df.groupby(available)
        .agg(congestion_avg=("congestion_weighted_avg", "mean"))
        .reset_index()
    )

    # Build alighting cache: (station, hour) → congestion level
    # Higher congestion = more activity = more alighting potential
    cache = {}
    for _, row in hourly.iterrows():
        station = row["station_normalized"]
        hour = int(row["hour"])
        val = row["congestion_avg"]

        key = (station, hour)
        if key in cache:
            # Average across directions
            cache[key] = (cache[key] + val) / 2
        else:
            cache[key] = val

    return cache, hourly


def build_congestion_long_compatible(congestion_30min):
    """
    Build a congestion_long.csv compatible with existing SeatScore engine.

    The existing engine expects:
      station_normalized, hour, type (boarding/alighting), count
    """
    df = congestion_30min.copy()

    # Filter weekday
    if "day_type" in df.columns:
        weekday = df[df["day_type"] == "평일"]
        if len(weekday) > 0:
            df = weekday

    # Group by station and hour (average 30-min slots)
    group_cols = ["station_normalized", "hour"]
    available = [c for c in group_cols if c in df.columns]

    hourly = (
        df.groupby(available)
        .agg(congestion=("congestion_weighted_avg", "mean"))
        .reset_index()
    )

    # Convert congestion percentage to passenger count estimate
    # Line 2: 10-car train, ~160 seats per car = 1600 seats
    # 100% congestion = all seats occupied = ~1600 passengers
    SEATS_PER_TRAIN = 1600
    hourly["estimated_passengers"] = hourly["congestion"] / 100.0 * SEATS_PER_TRAIN

    # Create boarding/alighting rows for compatibility
    # Approximate: alighting ≈ congestion drop, boarding ≈ congestion rise
    # For now, use congestion level as proxy for both
    rows = []
    for _, row in hourly.iterrows():
        station = row["station_normalized"]
        hour = int(row["hour"])
        passengers = row["estimated_passengers"]

        rows.append(
            {
                "station_normalized": station,
                "hour": hour,
                "type": "alighting",
                "count": passengers * 0.3,  # ~30% alight at typical station
            }
        )
        rows.append(
            {
                "station_normalized": station,
                "hour": hour,
                "type": "boarding",
                "count": passengers * 0.3,
            }
        )

    result = pd.DataFrame(rows)

    # Add time features for compatibility
    result["hour_sin"] = np.sin(2 * np.pi * result["hour"] / 24)
    result["hour_cos"] = np.cos(2 * np.pi * result["hour"] / 24)
    result["time_minutes"] = result["hour"] * 60
    result["is_morning_rush"] = result["hour"].isin([7, 8, 9]).astype(int)
    result["is_evening_rush"] = result["hour"].isin([18, 19, 20]).astype(int)
    result["is_night"] = ((result["hour"] >= 22) | (result["hour"] <= 5)).astype(int)

    return result


def main():
    input_dir = PROJECT_ROOT / "inputs" / "input_260207"
    output_dir = PROJECT_ROOT / "data_processed"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("PROCESSING NEW CONGESTION DATA")
    print("=" * 60)

    # Step 1: Load and combine all files
    combined = process_all_files(input_dir)
    if len(combined) == 0:
        print("No data to process!")
        return

    # Step 2: Build weighted averages
    print("\n--- Building weighted averages ---")
    weighted = build_weighted_average(combined)
    print(f"Weighted data: {len(weighted)} rows")

    # Step 3: Save 30-min granularity data
    out_30min = output_dir / "congestion_30min.csv"
    weighted.to_csv(out_30min, index=False, encoding="utf-8-sig")
    print(f"Saved 30-min data: {out_30min}")

    # Step 4: Build hourly alighting cache
    print("\n--- Building hourly alighting cache ---")
    cache, hourly = build_hourly_alighting_proxy(weighted)
    print(f"Cache entries: {len(cache)}")

    # Save cache
    cache_path = output_dir / "alighting_cache.pkl"
    with open(cache_path, "wb") as f:
        pickle.dump(cache, f)
    print(f"Saved cache: {cache_path}")

    # Step 5: Build backward-compatible congestion_long.csv
    print("\n--- Building compatible congestion_long.csv ---")
    compat = build_congestion_long_compatible(weighted)
    compat_path = output_dir / "congestion_long.csv"
    compat.to_csv(compat_path, index=False, encoding="utf-8-sig")
    print(f"Saved compatible data: {compat_path} ({len(compat)} rows)")

    # Step 6: Summary
    print("\n" + "=" * 60)
    print("PROCESSING COMPLETE")
    print("=" * 60)
    print(f"  30-min data: {out_30min}")
    print(f"  Hourly cache: {cache_path} ({len(cache)} entries)")
    print(f"  Compatible CSV: {compat_path} ({len(compat)} rows)")
    print(f"  Stations: {weighted['station_normalized'].nunique()}")

    # Show sample
    print("\n--- Sample stations and congestion (8AM weekday) ---")
    sample = weighted[
        (weighted["hour"] == 8) & (weighted["minute"] == 0)
    ]
    if "direction" in sample.columns:
        sample = sample[sample["direction"].str.contains("내", na=False)]
    for _, row in sample.head(10).iterrows():
        print(
            f"  {row['station_normalized']:>10s} | "
            f"congestion: {row['congestion_weighted_avg']:.1f}%"
        )


if __name__ == "__main__":
    main()
