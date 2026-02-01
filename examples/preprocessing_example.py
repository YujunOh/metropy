"""
Example usage of Metropy preprocessing pipeline
"""

from src.preprocessing import MetropyPreprocessor

# Example 1: Basic usage with auto-detection of files
print("Example 1: Running full pipeline with auto-detection")
print("="*60)
preprocessor = MetropyPreprocessor()
datasets = preprocessor.run_full_pipeline(save=True)

# Example 2: Specify custom file paths
print("\n\nExample 2: Custom file paths")
print("="*60)
preprocessor2 = MetropyPreprocessor()
datasets2 = preprocessor2.run_full_pipeline(
    fast_exit_path="data/raw/fast_exit.json",
    congestion_path="data/raw/congestion.csv",
    station_master_path="data/raw/station_master.csv",
    distance_path="data/raw/distance.csv",
    save=True
)

# Example 3: Load individual datasets without saving
print("\n\nExample 3: Load individual datasets")
print("="*60)
preprocessor3 = MetropyPreprocessor()
congestion = preprocessor3.load_congestion_data()
fast_exit = preprocessor3.load_fast_exit_data()
print(f"Congestion data shape: {congestion.shape if congestion is not None else 'None'}")
print(f"Fast Exit data shape: {fast_exit.shape if fast_exit is not None else 'None'}")

# Example 4: Use normalize_station_name utility
print("\n\nExample 4: Station name normalization")
print("="*60)
test_names = ["강남역", "서울역(1호선)", "홍대입구역 (2호선)", "  잠실역  "]
for name in test_names:
    normalized = MetropyPreprocessor.normalize_station_name(name)
    print(f"  {name:20s} -> {normalized}")