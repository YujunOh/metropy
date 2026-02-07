# AGENTS.md - Metropy Project Guide

This file contains instructions for agentic coding agents working on the Metropy data analysis project.

## Project Overview

Metropy is a Korean-language data analysis project focused on transportation and metro data analysis. The project uses pandas, matplotlib, seaborn, and scikit-learn for data processing, visualization, and machine learning.

## Build/Development Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start Jupyter Notebook
jupyter notebook
```

### Testing Commands
This project does not currently have automated tests. When implementing new features:
1. Test data processing functions manually in Jupyter notebooks
2. Validate visualizations render correctly with Korean fonts
3. Verify CSV encoding handling for Korean data (cp949, euc-kr, utf-8)

### Data Analysis Workflow
```bash
# Start analysis in notebooks directory
cd notebooks
jupyter notebook

# Use 00_getting_started.ipynb as template for new analysis
```

## Code Style Guidelines

### File Encoding and Headers
- All Python files must start with `# -*- coding: utf-8 -*-`
- Include descriptive docstrings for all functions
- Use Korean for comments and documentation when appropriate

### Import Organization
```python
# Standard library imports
import csv
from pathlib import Path
import sys

# Third-party imports
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split

# Local imports (when implemented)
from src.data import process_data
from src.visualization import create_plot
```

### Naming Conventions
- **Variables and functions**: `snake_case` (e.g., `process_data`, `file_path`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_ENCODING`, `DATA_DIR`)
- **Classes**: `PascalCase` (e.g., `DataProcessor`, `VisualizationHelper`)
- **File names**: `snake_case.py` (e.g., `data_loader.py`, `plot_generator.py`)

### Data Handling Patterns
- Always handle Korean text encodings: `['utf-8-sig', 'cp949', 'utf-8', 'euc-kr']`
- Use `pathlib.Path` for file operations instead of string paths
- Process large CSV files in chunks to avoid memory issues
- Save processed data as UTF-8 encoded files

### Error Handling
```python
try:
    # Data processing code
    with open(file_path, 'r', encoding=encoding) as f:
        data = process_file(f)
except UnicodeDecodeError:
    print(f"[ERROR] Encoding failed for {encoding}")
    continue
except Exception as e:
    print(f"[ERROR] {str(e)[:50]}")  # Truncate long error messages
```

### Visualization Standards
- Set Korean font support: `plt.rcParams['font.family'] = 'Malgun Gothic'`
- Always include: `plt.rcParams['axes.unicode_minus'] = False`
- Use figure sizes appropriate for reports: `plt.figure(figsize=(10, 6))`
- Include descriptive titles and axis labels in Korean

### Data Structure Patterns
```python
# Function returns for data processing
return {
    'encoding': encoding,
    'rows': row_count,
    'columns': len(header),
    'header': header,
    'data': processed_data
}

# Logging format for progress tracking
print(f"[SUCCESS] Operation completed: {operation_name}")
print(f"[WARN] Warning message: {warning_details}")
print(f"[ERROR] Error occurred: {error_message}")
```

### Project Structure Guidelines
- Place raw data in `data/raw/` (gitignored)
- Save processed data to `data/processed/` (gitignored)
- Store generated plots in `plots/` (gitignored)
- Keep analysis notebooks in `notebooks/`
- Utility scripts go in `scripts/`
- Reusable modules in `src/` with appropriate subdirectories

### Korean Text Handling
- CSV files may use cp949 or euc-kr encoding
- Always save processed files as utf-8-sig
- Handle mixed encoding gracefully with fallback options
- Test with actual Korean data files to ensure proper display

### Memory Management
- Use chunking for large file processing
- Close file handles explicitly with context managers
- Free memory for large DataFrames when no longer needed
- Use progress indicators for long-running operations

### Code Documentation
- Use Korean for user-facing messages and comments
- Keep function descriptions concise but informative
- Include parameter types and return value descriptions
- Example usage in docstrings for complex functions

## Development Workflow

1. **Data Discovery**: Use `scripts/analyze_large_files.py` to understand new datasets
2. **Encoding Issues**: Use `scripts/fix_encoding.py` for CSV encoding problems
3. **Analysis Development**: Create new notebooks in `notebooks/` directory
4. **Code Reuse**: Extract reusable functionality into `src/` modules
5. **Validation**: Test with real Korean transportation data files

## Common Gotchas

- Windows file paths need proper escaping or raw strings
- Korean font display requires specific matplotlib configuration
- CSV encoding can vary between files - always try multiple encodings
- Large transportation datasets may cause memory issues
- Jupyter notebooks should be cleaned of output before committing