"""
Encoding Fix Script
Read CSV files with various encodings
"""

import csv
from pathlib import Path

def try_read_csv(file_path, encodings=['cp949', 'euc-kr', 'utf-8', 'utf-8-sig', 'latin1']):
    """Try to read CSV with different encodings"""
    file_path = Path(file_path)

    print(f"\n{'='*60}")
    print(f"File: {file_path.name}")
    print(f"Size: {file_path.stat().st_size / 1024:.2f} KB")
    print(f"{'='*60}")

    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                print(f"[WARN] {encoding}: Empty file")
                continue

            print(f"\n[SUCCESS] Encoding: {encoding}")
            print(f"\nData Structure:")
            print(f"  - Rows: {len(rows):,}")
            print(f"  - Columns: {len(rows[0]) if rows else 0}")

            print(f"\nColumn Names (first row):")
            for i, col in enumerate(rows[0], 1):
                print(f"  {i}. {col}")

            print(f"\nFirst 5 Rows Preview:")
            for i, row in enumerate(rows[:6], 0):
                if i == 0:
                    print(f"  [HEADER] {', '.join(row[:5])}")
                else:
                    print(f"  [ROW {i}] {', '.join(row[:5])}")

            # Save as UTF-8
            output_path = file_path.parent / f"{file_path.stem}_utf8.csv"
            with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            print(f"\n[SAVED] UTF-8 file: {output_path.name}")

            return rows, encoding

        except UnicodeDecodeError:
            print(f"[FAIL] {encoding} - UnicodeDecodeError")
        except Exception as e:
            print(f"[ERROR] {encoding} - {str(e)[:50]}")

    print(f"\n[FAIL] All encodings failed!")
    return None, None

# Problem files
files = [
    r"c:\PROGRAMMING\2026_1_SPRING\metropy\inputs\line9_interstation_distance.csv",
    r"c:\PROGRAMMING\2026_1_SPRING\metropy\inputs\interStation_distance_time_20240810.csv",
    r"c:\PROGRAMMING\2026_1_SPRING\metropy\inputs\station_master.csv"
]

results = {}
for file_path in files:
    rows, encoding = try_read_csv(file_path)
    if rows is not None:
        results[Path(file_path).name] = {
            'encoding': encoding,
            'shape': (len(rows), len(rows[0]) if rows else 0),
            'columns': rows[0] if rows else []
        }

print(f"\n\n{'='*60}")
print("[SUMMARY] All Files")
print(f"{'='*60}")
for fname, info in results.items():
    print(f"\n{fname}:")
    print(f"  Encoding: {info['encoding']}")
    print(f"  Shape: {info['shape'][0]} rows x {info['shape'][1]} columns")
    print(f"  Columns: {len(info['columns'])}")

