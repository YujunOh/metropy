# Metropy Preprocessing Module

This module provides comprehensive data preprocessing for the Metropy transit analysis project.

## Features

1. **Fast Exit Data Loading**: Load and process Fast Exit information from JSON files
2. **Congestion Data Transformation**: Convert wide-format data to long format
3. **Cyclical Time Features**: Add sin/cos transformations for hour-of-day
4. **Station Name Normalization**: Clean Korean station names (remove 역, parentheses, etc.)
5. **Master Dataset Creation**: Integrate all data sources into a single dataset
6. **Auto-detection**: Automatically find data files in data_raw/ directory

## Quick Start

```python
from src.preprocessing import MetropyPreprocessor

# Initialize and run full pipeline
preprocessor = MetropyPreprocessor()
datasets = preprocessor.run_full_pipeline(save=True)

# Access individual datasets
congestion_data = datasets['congestion']
fast_exit_data = datasets['fast_exit']
master_dataset = datasets['master_dataset']
```

## Key Methods

### MetropyPreprocessor

- `load_fast_exit_data()` - Load Fast Exit data from JSON
- `load_congestion_data()` - Transform wide to long format
- `load_station_master()` - Load station metadata
- `load_distance_data()` - Load interstation distances
- `create_master_dataset()` - Merge all data sources
- `save_processed_data()` - Save to data_processed/
- `run_full_pipeline()` - Execute complete pipeline
- `normalize_station_name()` - Static method for name cleaning

## Output Files

Processed data is saved to `data_processed/`:

- processed_fast_exit.csv
- processed_congestion.csv
- processed_station_master.csv
- processed_distance.csv
- processed_master_dataset.csv

## Dependencies

- pandas
- numpy
- json
- pathlib
- re
