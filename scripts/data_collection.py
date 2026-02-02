# -*- coding: utf-8 -*-
"""
Data Collection Module
Fetch data from Fast Exit API and save to data/raw
"""

import urllib.request
import json
from pathlib import Path
from time import sleep

# API Configuration
API_KEY = "4a6151427564627737397053547256"
BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/getFstExit"

def fetch_fast_exit_data(start_idx=1, end_idx=1000, save_path=None):
    """
    Fetch Fast Exit API data
    
    Args:
        start_idx: Start index (1-based)
        end_idx: End index
        save_path: Path to save JSON file
    
    Returns:
        list: Records from API
    """
    url = f"{BASE_URL}/{start_idx}/{end_idx}/"
    
    print(f"Fetching data from API: {start_idx} to {end_idx}")
    
    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=30) as response:
            raw_data = response.read()
            
            # Handle encoding
            try:
                text_data = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                text_data = raw_data.decode('cp949')
            
            data = json.loads(text_data)
            
            # Navigate to records
            if 'response' in data:
                response_data = data['response']
                
                # Check header
                if 'header' in response_data:
                    header = response_data['header']
                    if header.get('resultCode') != '00':
                        print(f"API Error: {header.get('resultMsg')}")
                        return []
                
                # Get records
                if 'body' in response_data and 'items' in response_data['body']:
                    items = response_data['body']['items']
                    
                    if 'item' in items:
                        records = items['item']
                        print(f"Successfully fetched {len(records)} records")
                        
                        # Save if path provided
                        if save_path:
                            save_path = Path(save_path)
                            save_path.parent.mkdir(parents=True, exist_ok=True)
                            
                            with open(save_path, 'w', encoding='utf-8') as f:
                                json.dump(records, f, ensure_ascii=False, indent=2)
                            print(f"Saved to: {save_path}")
                        
                        return records
            
            print("No data found in response")
            return []
            
    except Exception as e:
        print(f"Error fetching data: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def fetch_all_fast_exit_data(batch_size=1000, max_records=5000, save_dir="data/raw"):
    """
    Fetch all Fast Exit API data in batches
    
    Args:
        batch_size: Records per request
        max_records: Maximum total records to fetch
        save_dir: Directory to save results
    
    Returns:
        list: All records
    """
    all_records = []
    save_dir = Path(save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    for start in range(1, max_records, batch_size):
        end = min(start + batch_size - 1, max_records)
        
        print(f"\n--- Batch {start} to {end} ---")
        
        batch_records = fetch_fast_exit_data(
            start_idx=start,
            end_idx=end,
            save_path=save_dir / f"fast_exit_batch_{start}_{end}.json"
        )
        
        if not batch_records:
            print("No more data available")
            break
        
        all_records.extend(batch_records)
        
        # Respect API rate limit
        sleep(1)
        
        # Stop if we got less than requested (end of data)
        if len(batch_records) < batch_size:
            print(f"Received {len(batch_records)} < {batch_size}, stopping")
            break
    
    # Save combined data
    combined_path = save_dir / "fast_exit_all.json"
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)
    
    print(f"\n=== COMPLETE ===")
    print(f"Total records fetched: {len(all_records)}")
    print(f"Saved to: {combined_path}")
    
    return all_records

def filter_line2_data(records):
    """
    Filter records for Line 2 only
    
    Args:
        records: All records from API
    
    Returns:
        list: Line 2 records only
    """
    line2_records = [r for r in records if '2호선' in r.get('lineNm', '')]
    
    print(f"Filtered Line 2: {len(line2_records)} records (from {len(records)} total)")
    
    # Statistics
    if line2_records:
        stations = set(r.get('stnNm') for r in line2_records)
        cars = set(r.get('qckgffVhclDoorNo') for r in line2_records)
        
        print(f"  - Unique stations: {len(stations)}")
        print(f"  - Unique car configs: {len(cars)}")
    
    return line2_records

if __name__ == "__main__":
    print("="*70)
    print("FAST EXIT API DATA COLLECTION")
    print("="*70)
    
    # Fetch all data
    all_records = fetch_all_fast_exit_data(
        batch_size=1000,
        max_records=5000,
        save_dir="../data/raw"
    )
    
    # Filter Line 2
    line2_records = filter_line2_data(all_records)
    
    # Save Line 2 data
    line2_path = Path("../data/raw/fast_exit_line2.json")
    with open(line2_path, 'w', encoding='utf-8') as f:
        json.dump(line2_records, f, ensure_ascii=False, indent=2)
    
    print(f"\nLine 2 data saved to: {line2_path}")
    print("\nNext: Run data preprocessing pipeline")
