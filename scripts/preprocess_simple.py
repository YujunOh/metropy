# -*- coding: utf-8 -*-
"""
Simple Preprocessing for Metropy Line 2 Data
"""

import pandas as pd
import numpy as np
import json
import re
from pathlib import Path

def normalize_station_name(name):
    """Remove 역, parentheses, spaces from station names"""
    if pd.isna(name):
        return ""
    name = str(name)
    name = re.sub(r'\([^)]*\)', '', name)
    name = name.replace('역', '').replace(' ', '').strip()
    return name

# Paths
data_raw = Path("../data/raw")
data_processed = Path("../data/processed")
data_processed.mkdir(exist_ok=True)

print("="*70)
print("METROPY LINE 2 PREPROCESSING")
print("="*70)

# 1. Load Fast Exit JSON (list of records)
print("\n1. Loading Fast Exit data...")
with open(data_raw / "fast_exit_line2.json", 'r', encoding='utf-8') as f:
    fast_exit_list = json.load(f)

df_fast_exit = pd.DataFrame(fast_exit_list)
df_fast_exit['station_normalized'] = df_fast_exit['stnNm'].apply(normalize_station_name)
print(f"   Loaded: {len(df_fast_exit)} records")
print(f"   Columns: {list(df_fast_exit.columns)[:8]}...")

# Save processed
df_fast_exit.to_csv(data_processed / "fast_exit_processed.csv", index=False, encoding='utf-8-sig')

# 2. Load Congestion CSV and transform wide -> long
print("\n2. Loading Congestion data...")
df_cong = pd.read_csv(data_raw / "hourly_line2_station_cnt.csv", encoding='utf-8-sig')
print(f"   Loaded: {len(df_cong)} rows x {len(df_cong.columns)} columns")

# Find time columns
time_cols = [col for col in df_cong.columns if '시' in col and ('승차' in col or '하차' in col)]
id_cols = [col for col in df_cong.columns if col not in time_cols]
print(f"   Time columns: {len(time_cols)}")

# Melt to long format
df_cong_long = pd.melt(
    df_cong,
    id_vars=id_cols,
    value_vars=time_cols,
    var_name='time_type',
    value_name='count'
)

# Parse hour and type
def parse_time(s):
    if pd.isna(s):
        return None, None
    s = str(s)
    hour_match = re.search(r'(\d+)시', s)
    hour = int(hour_match.group(1)) if hour_match else None
    type_str = 'boarding' if '승차' in s else 'alighting' if '하차' in s else 'unknown'
    return hour, type_str

df_cong_long[['hour', 'type']] = df_cong_long['time_type'].apply(lambda x: pd.Series(parse_time(x)))
df_cong_long = df_cong_long[df_cong_long['hour'].notna()].copy()
df_cong_long['count'] = pd.to_numeric(df_cong_long['count'], errors='coerce')
df_cong_long = df_cong_long[df_cong_long['count'].notna()].copy()

# Normalize station names
station_col = [col for col in id_cols if '역' in col or 'station' in col.lower()][0]
df_cong_long['station_normalized'] = df_cong_long[station_col].apply(normalize_station_name)

print(f"   After transform: {len(df_cong_long)} rows")
print(f"   Unique stations: {df_cong_long['station_normalized'].nunique()}")

# Add time features
df_cong_long['time_minutes'] = df_cong_long['hour'] * 60
df_cong_long['hour_sin'] = np.sin(2 * np.pi * df_cong_long['hour'] / 24)
df_cong_long['hour_cos'] = np.cos(2 * np.pi * df_cong_long['hour'] / 24)
df_cong_long['is_morning_rush'] = ((df_cong_long['hour'] >= 7) & (df_cong_long['hour'] < 9)).astype(int)
df_cong_long['is_evening_rush'] = ((df_cong_long['hour'] >= 18) & (df_cong_long['hour'] < 20)).astype(int)
df_cong_long['is_night'] = ((df_cong_long['hour'] >= 22) | (df_cong_long['hour'] < 6)).astype(int)

# Save processed
df_cong_long.to_csv(data_processed / "congestion_long.csv", index=False, encoding='utf-8-sig')

# 3. Load Station Master
print("\n3. Loading Station Master...")
df_stations = pd.read_csv(data_raw / "station_master.csv", encoding='utf-8-sig')
station_name_col = [col for col in df_stations.columns if '역' in col or '이름' in col][0]
df_stations['station_normalized'] = df_stations[station_name_col].apply(normalize_station_name)
print(f"   Loaded: {len(df_stations)} stations")

df_stations.to_csv(data_processed / "station_master_processed.csv", index=False, encoding='utf-8-sig')

# 4. Load Interstation Distance
print("\n4. Loading Interstation Distance...")
df_distance = pd.read_csv(data_raw / "interstation_distance_time.csv", encoding='utf-8-sig')
station_col_dist = [col for col in df_distance.columns if '역' in col][0]
df_distance['station_normalized'] = df_distance[station_col_dist].apply(normalize_station_name)
distance_col = [col for col in df_distance.columns if '거리' in col or 'distance' in col.lower()][0]
df_distance['cumulative_distance'] = df_distance[distance_col].cumsum()
print(f"   Loaded: {len(df_distance)} segments")

df_distance.to_csv(data_processed / "interstation_distance_processed.csv", index=False, encoding='utf-8-sig')

# 5. Create Master Dataset
print("\n5. Creating Master Dataset...")
df_master = df_cong_long.copy()

# Merge station master
df_master = df_master.merge(
    df_stations[['station_normalized', '위도', '경도']],
    on='station_normalized',
    how='left'
)

# Merge distance
df_master = df_master.merge(
    df_distance[['station_normalized', 'cumulative_distance']],
    on='station_normalized',
    how='left'
)

print(f"   Master dataset: {len(df_master)} rows x {len(df_master.columns)} columns")

# Save master
df_master.to_csv(data_processed / "master_dataset.csv", index=False, encoding='utf-8-sig')

print("\n" + "="*70)
print("PREPROCESSING COMPLETE!")
print("="*70)
print(f"\nOutput files in {data_processed}:")
for f in sorted(data_processed.glob("*.csv")):
    print(f"  - {f.name} ({f.stat().st_size / 1024:.1f} KB)")

print(f"\nMaster dataset columns ({len(df_master.columns)}):")
for col in df_master.columns:
    print(f"  - {col}")

print(f"\nSample statistics:")
print(f"  Stations: {df_master['station_normalized'].nunique()}")
print(f"  Hours: {df_master['hour'].nunique()}")
print(f"  Types: {df_master['type'].unique()}")
