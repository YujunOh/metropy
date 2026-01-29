"""
Metropy Data Preprocessing Pipeline
====================================
This module handles data loading, transformation, and preparation for the Metropy project.
Includes congestion data, Fast Exit information, station metadata, and distance calculations.
"""

import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
from src.utils import normalize_station_name as _normalize_util


class MetropyPreprocessor:
    """
    Main preprocessing class for Metropy transit data analysis.
    
    Handles:
    - Loading Fast Exit data from JSON
    - Transforming congestion data from wide to long format
    - Adding cyclical time features
    - Integrating station master data
    - Computing interstation distances
    - Normalizing Korean station names
    """
    
    def __init__(self, base_path: str = None):
        """
        Initialize the preprocessor.
        
        Args:
            base_path: Base directory path for the project. 
                      Defaults to parent of src/ directory.
        """
        if base_path is None:
            self.base_path = Path(__file__).parent.parent
        else:
            self.base_path = Path(base_path)
        
        self.data_raw_path = self.base_path / "data_raw"
        self.data_processed_path = self.base_path / "data_processed"
        
        # Create processed data directory if it doesn't exist
        self.data_processed_path.mkdir(parents=True, exist_ok=True)
        
        # Data containers
        self.fast_exit_data = None
        self.congestion_data = None
        self.station_master = None
        self.distance_data = None
        self.master_dataset = None
        
        print(f"MetropyPreprocessor initialized")
        print(f"Base path: {self.base_path}")
        print(f"Raw data path: {self.data_raw_path}")
        print(f"Processed data path: {self.data_processed_path}")
    
    @staticmethod
    def normalize_station_name(name: str) -> str:
        """
        Normalize Korean station names by removing common suffixes and formatting.
        
        Delegates to src.utils.normalize_station_name for canonical implementation.
        """
        from src.utils import normalize_station_name as _normalize
        return _normalize(name) if not pd.isna(name) else name    
        """
        Load Fast Exit data from JSON file.
        
        Expected JSON structure:
        {
            "station_name": {
                "line": "line_number",
                "fast_exits": ["exit_1", "exit_2", ...]
            }
        }
        
        Args:
            filepath: Path to JSON file. If None, searches in data_raw/
            
        Returns:
            DataFrame with columns: station, line, exit_number, is_fast_exit
        """
        if filepath is None:
            # Try common filenames
            possible_files = [
                self.data_raw_path / "fast_exit.json",
                self.data_raw_path / "fast_exit_data.json",
                self.data_raw_path / "fastexit.json"
            ]
            filepath = next((f for f in possible_files if f.exists()), None)
            
            if filepath is None:
                print("Warning: Fast Exit JSON file not found. Skipping.")
                return pd.DataFrame()
        
        print(f"Loading Fast Exit data from: {filepath}")
        
        with open(filepath, 'r', encoding='utf-8') as f:
            fast_exit_json = json.load(f)
        
        # Transform to DataFrame
        records = []
        for station, info in fast_exit_json.items():
            line = info.get('line', 'Unknown')
            fast_exits = info.get('fast_exits', [])
            
            # Normalize station name
            normalized_station = self.normalize_station_name(station)
            
            for exit_num in fast_exits:
                records.append({
                    'station': normalized_station,
                    'station_original': station,
                    'line': line,
                    'exit_number': exit_num,
                    'is_fast_exit': 1
                })
        
        self.fast_exit_data = pd.DataFrame(records)
        print(f"Loaded {len(self.fast_exit_data)} Fast Exit records")
        
        return self.fast_exit_data
    
    def load_congestion_data(self, filepath: str = None) -> pd.DataFrame:
        """
        Load and transform congestion data from wide to long format.
        
        Expected format: Wide format with columns like 'hour_0530', 'hour_0600', etc.
        Transforms to long format with separate hour column.
        
        Args:
            filepath: Path to CSV file. If None, searches in data_raw/
            
        Returns:
            DataFrame in long format with congestion by hour
        """
        if filepath is None:
            # Try common filenames
            possible_files = [
                self.data_raw_path / "congestion.csv",
                self.data_raw_path / "congestion_data.csv",
                self.data_raw_path / "subway_congestion.csv"
            ]
            filepath = next((f for f in possible_files if f.exists()), None)
            
            if filepath is None:
                print("Warning: Congestion CSV file not found. Skipping.")
                return pd.DataFrame()
        
        print(f"Loading congestion data from: {filepath}")
        
        # Load data
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # Identify hour columns (assuming format like 'hour_0530', 'hour_0600')
        hour_cols = [col for col in df.columns if col.startswith('hour_')]
        id_cols = [col for col in df.columns if col not in hour_cols]
        
        print(f"Found {len(hour_cols)} hour columns and {len(id_cols)} ID columns")
        
        # Transform from wide to long
        df_long = pd.melt(
            df,
            id_vars=id_cols,
            value_vars=hour_cols,
            var_name='hour_str',
            value_name='congestion_level'
        )
        
        # Extract hour as integer (e.g., 'hour_0530' -> 5, 'hour_1730' -> 17)
        df_long['hour'] = df_long['hour_str'].str.extract(r'hour_(\d{2})').astype(int)
        df_long['minute'] = df_long['hour_str'].str.extract(r'hour_\d{2}(\d{2})').astype(int)
        
        # Add cyclical time features
        df_long = self.add_cyclical_features(df_long)
        
        # Normalize station names if station column exists
        if 'station' in df_long.columns:
            df_long['station_original'] = df_long['station']
            df_long['station'] = df_long['station'].apply(self.normalize_station_name)
        
        self.congestion_data = df_long
        print(f"Transformed to long format: {len(self.congestion_data)} records")
        
        return self.congestion_data
    
    @staticmethod
    def add_cyclical_features(df: pd.DataFrame, hour_col: str = 'hour') -> pd.DataFrame:
        """
        Add cyclical sine and cosine features for hour of day.
        
        This ensures that 23:00 and 00:00 are treated as close together.
        
        Args:
            df: DataFrame with hour column
            hour_col: Name of hour column
            
        Returns:
            DataFrame with added hour_sin and hour_cos columns
        """
        if hour_col not in df.columns:
            print(f"Warning: Column '{hour_col}' not found. Skipping cyclical features.")
            return df
        
        # Convert hour to radians (24 hours = 2π)
        df['hour_sin'] = np.sin(2 * np.pi * df[hour_col] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df[hour_col] / 24)
        
        print(f"Added cyclical features: hour_sin, hour_cos")
        
        return df    
    def load_station_master(self, filepath: str = None) -> pd.DataFrame:
        """
        Load station master data with metadata (coordinates, line info, etc.).
        
        Args:
            filepath: Path to CSV file. If None, searches in data_raw/
            
        Returns:
            DataFrame with station metadata
        """
        if filepath is None:
            # Try common filenames
            possible_files = [
                self.data_raw_path / "station_master.csv",
                self.data_raw_path / "stations.csv",
                self.data_raw_path / "station_info.csv"
            ]
            filepath = next((f for f in possible_files if f.exists()), None)
            
            if filepath is None:
                print("Warning: Station master CSV file not found. Skipping.")
                return pd.DataFrame()
        
        print(f"Loading station master data from: {filepath}")
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # Normalize station names
        if 'station' in df.columns:
            df['station_original'] = df['station']
            df['station'] = df['station'].apply(self.normalize_station_name)
        elif 'station_name' in df.columns:
            df['station_original'] = df['station_name']
            df['station'] = df['station_name'].apply(self.normalize_station_name)
        
        self.station_master = df
        print(f"Loaded {len(self.station_master)} stations")
        
        return self.station_master
    
    def load_distance_data(self, filepath: str = None) -> pd.DataFrame:
        """
        Load interstation distance data.
        
        Expected columns: station_from, station_to, distance_km, travel_time_min
        
        Args:
            filepath: Path to CSV file. If None, searches in data_raw/
            
        Returns:
            DataFrame with distance information
        """
        if filepath is None:
            # Try common filenames
            possible_files = [
                self.data_raw_path / "distance.csv",
                self.data_raw_path / "interstation_distance.csv",
                self.data_raw_path / "station_distance.csv"
            ]
            filepath = next((f for f in possible_files if f.exists()), None)
            
            if filepath is None:
                print("Warning: Distance CSV file not found. Skipping.")
                return pd.DataFrame()
        
        print(f"Loading distance data from: {filepath}")
        
        df = pd.read_csv(filepath, encoding='utf-8-sig')
        
        # Normalize station names
        if 'station_from' in df.columns:
            df['station_from_original'] = df['station_from']
            df['station_from'] = df['station_from'].apply(self.normalize_station_name)
        
        if 'station_to' in df.columns:
            df['station_to_original'] = df['station_to']
            df['station_to'] = df['station_to'].apply(self.normalize_station_name)
        
        self.distance_data = df
        print(f"Loaded {len(self.distance_data)} distance records")
        
        return self.distance_data
    
    def create_master_dataset(self) -> pd.DataFrame:
        """
        Combine all data sources into a master dataset.
        
        Merges:
        - Congestion data (base)
        - Fast Exit data
        - Station master data
        - Distance data (if applicable)
        
        Returns:
            Integrated master dataset
        """
        print("\n" + "="*60)
        print("Creating Master Dataset")
        print("="*60)
        
        if self.congestion_data is None or len(self.congestion_data) == 0:
            print("Warning: No congestion data loaded. Master dataset will be empty.")
            return pd.DataFrame()
        
        # Start with congestion data as base
        master = self.congestion_data.copy()
        print(f"Base dataset (congestion): {len(master)} records")
        
        # Merge with Fast Exit data
        if self.fast_exit_data is not None and len(self.fast_exit_data) > 0:
            # Create a station-level fast exit indicator
            fast_exit_summary = self.fast_exit_data.groupby('station').agg({
                'is_fast_exit': 'count',  # Number of fast exits
                'exit_number': lambda x: ','.join(map(str, x))  # List of exits
            }).reset_index()
            fast_exit_summary.columns = ['station', 'num_fast_exits', 'fast_exit_list']
            
            master = master.merge(
                fast_exit_summary,
                on='station',
                how='left'
            )
            master['num_fast_exits'] = master['num_fast_exits'].fillna(0).astype(int)
            print(f"After merging Fast Exit data: {len(master)} records")
        
        # Merge with Station Master data
        if self.station_master is not None and len(self.station_master) > 0:
            merge_cols = ['station']
            if 'line' in master.columns and 'line' in self.station_master.columns:
                merge_cols.append('line')
            
            master = master.merge(
                self.station_master,
                on=merge_cols,
                how='left',
                suffixes=('', '_master')
            )
            print(f"After merging Station Master: {len(master)} records")
        
        self.master_dataset = master
        
        print("\nMaster Dataset Summary:")
        print(f"  Total records: {len(self.master_dataset)}")
        print(f"  Columns: {len(self.master_dataset.columns)}")
        print(f"  Unique stations: {self.master_dataset['station'].nunique() if 'station' in self.master_dataset.columns else 'N/A'}")
        print("="*60 + "\n")
        
        return self.master_dataset    
    def save_processed_data(self, prefix: str = "processed") -> Dict[str, Path]:
        """
        Save all processed datasets to CSV files.
        
        Args:
            prefix: Prefix for output filenames
            
        Returns:
            Dictionary mapping dataset name to saved filepath
        """
        print("\n" + "="*60)
        print("Saving Processed Data")
        print("="*60)
        
        saved_files = {}
        
        # Save Fast Exit data
        if self.fast_exit_data is not None and len(self.fast_exit_data) > 0:
            filepath = self.data_processed_path / f"{prefix}_fast_exit.csv"
            self.fast_exit_data.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files['fast_exit'] = filepath
            print(f"Saved Fast Exit data: {filepath}")
        
        # Save Congestion data
        if self.congestion_data is not None and len(self.congestion_data) > 0:
            filepath = self.data_processed_path / f"{prefix}_congestion.csv"
            self.congestion_data.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files['congestion'] = filepath
            print(f"Saved Congestion data: {filepath}")
        
        # Save Station Master
        if self.station_master is not None and len(self.station_master) > 0:
            filepath = self.data_processed_path / f"{prefix}_station_master.csv"
            self.station_master.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files['station_master'] = filepath
            print(f"Saved Station Master: {filepath}")
        
        # Save Distance data
        if self.distance_data is not None and len(self.distance_data) > 0:
            filepath = self.data_processed_path / f"{prefix}_distance.csv"
            self.distance_data.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files['distance'] = filepath
            print(f"Saved Distance data: {filepath}")
        
        # Save Master Dataset
        if self.master_dataset is not None and len(self.master_dataset) > 0:
            filepath = self.data_processed_path / f"{prefix}_master_dataset.csv"
            self.master_dataset.to_csv(filepath, index=False, encoding='utf-8-sig')
            saved_files['master_dataset'] = filepath
            print(f"Saved Master Dataset: {filepath}")
        
        print("="*60 + "\n")
        
        return saved_files
    
    def run_full_pipeline(self, 
                         fast_exit_path: str = None,
                         congestion_path: str = None,
                         station_master_path: str = None,
                         distance_path: str = None,
                         save: bool = True) -> Dict[str, pd.DataFrame]:
        """
        Run the complete preprocessing pipeline.
        
        Args:
            fast_exit_path: Path to Fast Exit JSON file
            congestion_path: Path to congestion CSV file
            station_master_path: Path to station master CSV file
            distance_path: Path to distance CSV file
            save: Whether to save processed data to files
            
        Returns:
            Dictionary of all processed datasets
        """
        print("\n" + "="*60)
        print("METROPY PREPROCESSING PIPELINE")
        print("="*60 + "\n")
        
        # Load all data sources
        self.load_fast_exit_data(fast_exit_path)
        self.load_congestion_data(congestion_path)
        self.load_station_master(station_master_path)
        self.load_distance_data(distance_path)
        
        # Create master dataset
        self.create_master_dataset()
        
        # Save if requested
        if save:
            self.save_processed_data()
        
        print("Pipeline completed successfully!\n")
        
        return {
            'fast_exit': self.fast_exit_data,
            'congestion': self.congestion_data,
            'station_master': self.station_master,
            'distance': self.distance_data,
            'master_dataset': self.master_dataset
        }


def main():
    """
    Main execution function for standalone script usage.
    """
    # Initialize preprocessor
    preprocessor = MetropyPreprocessor()
    
    # Run full pipeline
    datasets = preprocessor.run_full_pipeline(save=True)
    
    # Print summary statistics
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)
    
    for name, df in datasets.items():
        if df is not None and len(df) > 0:
            print(f"\n{name.upper()}:")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)[:10]}...")  # First 10 columns
            print(f"  Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
    
    print("\n" + "="*60)
    print("Preprocessing complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()