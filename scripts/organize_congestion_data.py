"""
Organize Congestion Data
Filter and copy Line 2 congestion data from inputs/ to data/raw/
"""

import pandas as pd
from pathlib import Path
import shutil

def analyze_congestion_xlsx():
    """Analyze the main congestion XLSX file"""
    xlsx_path = Path("../inputs/congestion_line9_weekday_weekend_station_hour.xlsx")
    
    if not xlsx_path.exists():
        print(f"[SKIP] {xlsx_path.name} not found")
        return None
    
    print(f"Analyzing: {xlsx_path.name}")
    
    try:
        # Read all sheets
        xl_file = pd.ExcelFile(xlsx_path)
        print(f"  Sheets: {xl_file.sheet_names}")
        
        # Check if it really only has Line 9 or has other lines too
        for sheet_name in xl_file.sheet_names[:3]:  # Check first 3 sheets
            df = pd.read_excel(xlsx_path, sheet_name=sheet_name, nrows=10)
            print(f"\n  Sheet '{sheet_name}' columns: {list(df.columns)[:5]}...")
            
            # Check if there's a line column
            if '호선' in df.columns or '노선' in df.columns or 'line' in str(df.columns).lower():
                line_col = [c for c in df.columns if '호선' in str(c) or '노선' in str(c) or 'line' in str(c).lower()][0]
                print(f"    Found line column: {line_col}")
                print(f"    Sample values: {df[line_col].unique()[:5]}")
        
        return xl_file
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        return None

def organize_hourly_station_data():
    """Organize hourly line station count data"""
    csv_path = Path("../inputs/hourly_line_station_cnt.csv")
    
    if not csv_path.exists():
        print(f"[SKIP] {csv_path.name} not found")
        return
    
    print(f"\nProcessing: {csv_path.name}")
    
    try:
        # Read with CP949 encoding
        df = pd.read_csv(csv_path, encoding='cp949')
        print(f"  Total rows: {len(df):,}")
        print(f"  Columns: {list(df.columns)[:5]}...")
        
        # Check line column name
        line_col = None
        for col in df.columns:
            if '호선' in col or '노선' in col:
                line_col = col
                break
        
        if line_col:
            print(f"  Line column: {line_col}")
            print(f"  Unique lines: {df[line_col].unique()}")
            
            # Filter Line 2
            df_line2 = df[df[line_col].str.contains('2호선', na=False)]
            print(f"  Line 2 rows: {len(df_line2):,}")
            
            if len(df_line2) > 0:
                # Save to data/raw
                output_path = Path("../data/raw/hourly_line2_station_cnt.csv")
                df_line2.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"  Saved to: {output_path}")
                return df_line2
        else:
            print("  [WARNING] No line column found")
    
    except Exception as e:
        print(f"  Error: {str(e)}")
        import traceback
        traceback.print_exc()

def organize_station_master():
    """Copy station master data"""
    src_path = Path("../inputs/station_master_utf8.csv")
    dst_path = Path("../data/raw/station_master.csv")
    
    if src_path.exists():
        print(f"\nCopying: {src_path.name}")
        
        # Read and filter Line 2
        df = pd.read_csv(src_path, encoding='utf-8-sig')
        
        # Check column names
        print(f"  Columns: {list(df.columns)}")
        
        # Filter Line 2 if possible
        line_col = None
        for col in df.columns:
            if '호선' in col or 'line' in col.lower():
                line_col = col
                break
        
        if line_col:
            df_line2 = df[df[line_col].str.contains('2', na=False)]
            print(f"  Line 2 stations: {len(df_line2)}")
            df_line2.to_csv(dst_path, index=False, encoding='utf-8-sig')
        else:
            # Copy all if we can't filter
            shutil.copy(src_path, dst_path)
        
        print(f"  Saved to: {dst_path}")

def organize_interstation_distance():
    """Copy inter-station distance data"""
    src_path = Path("../inputs/interStation_distance_time_20240810_utf8.csv")
    dst_path = Path("../data/raw/interstation_distance_time.csv")
    
    if src_path.exists():
        print(f"\nCopying: {src_path.name}")
        
        # Read and filter Line 2
        df = pd.read_csv(src_path, encoding='utf-8-sig')
        print(f"  Columns: {list(df.columns)}")
        print(f"  Total rows: {len(df)}")
        
        # Filter Line 2
        line_col = None
        for col in df.columns:
            if '호선' in col or 'line' in col.lower():
                line_col = col
                break
        
        if line_col:
            # Handle both string and integer line columns
            if df[line_col].dtype == 'int64' or df[line_col].dtype == 'int32':
                df_line2 = df[df[line_col] == 2]
            else:
                df_line2 = df[df[line_col].astype(str).str.contains('2', na=False)]
            print(f"  Line 2 rows: {len(df_line2)}")
            df_line2.to_csv(dst_path, index=False, encoding='utf-8-sig')
        else:
            shutil.copy(src_path, dst_path)
        
        print(f"  Saved to: {dst_path}")

def check_congestion_30min_files():
    """Check 30-minute congestion files"""
    congestion_dir = Path("../inputs/congestion_30min")
    
    if not congestion_dir.exists():
        print(f"[SKIP] {congestion_dir} not found")
        return
    
    print(f"\nChecking: {congestion_dir}")
    
    csv_files = list(congestion_dir.glob("*.csv"))
    xlsx_files = list(congestion_dir.glob("*.xlsx"))
    
    print(f"  CSV files: {len(csv_files)}")
    print(f"  XLSX files: {len(xlsx_files)}")
    
    # Try to read one CSV file
    if csv_files:
        sample_file = csv_files[0]
        print(f"\n  Sampling: {sample_file.name}")
        
        try:
            df = pd.read_csv(sample_file, encoding='cp949', nrows=10)
            print(f"    Columns: {list(df.columns)[:5]}...")
            
            # Check if there's a line filter
            for col in df.columns:
                if '호선' in col or '노선' in col:
                    print(f"    Line column: {col}")
                    print(f"    Sample values: {df[col].unique()}")
        
        except Exception as e:
            print(f"    Error: {str(e)}")

if __name__ == "__main__":
    print("="*70)
    print("ORGANIZING CONGESTION DATA FOR LINE 2")
    print("="*70)
    
    # Create data/raw if not exists
    Path("../data/raw").mkdir(parents=True, exist_ok=True)
    
    # Analyze and organize data
    analyze_congestion_xlsx()
    organize_hourly_station_data()
    organize_station_master()
    organize_interstation_distance()
    check_congestion_30min_files()
    
    print("\n" + "="*70)
    print("ORGANIZATION COMPLETE")
    print("="*70)
    print("\nNext steps:")
    print("  1. Check data/raw/ directory")
    print("  2. Create preprocessing pipeline")
    print("  3. Begin EDA in Jupyter notebook")
