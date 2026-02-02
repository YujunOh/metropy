# -*- coding: utf-8 -*-
"""
Fast Exit API Tester
Test Seoul Metro Fast Exit API to check line availability
"""

import urllib.request
import json
from time import sleep

# API Configuration
API_KEY = "4a6151427564627737397053547256"
BASE_URL = f"http://openapi.seoul.go.kr:8088/{API_KEY}/json/getFstExit"

def test_api_connection():
    """Test basic API connectivity and show sample data"""
    print("="*70)
    print("TESTING API CONNECTION")
    print("="*70)

    test_url = f"{BASE_URL}/1/5/"
    print(f"\nTest URL: {test_url}")

    try:
        request = urllib.request.Request(test_url)
        with urllib.request.urlopen(request, timeout=10) as response:
            # Read with proper encoding handling
            raw_data = response.read()

            # Try UTF-8 first, then CP949
            try:
                text_data = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                text_data = raw_data.decode('cp949')

            data = json.loads(text_data)

            print("\n[SUCCESS] API is accessible!")

            # Navigate to actual data
            if 'response' in data:
                response_data = data['response']

                if 'header' in response_data:
                    header = response_data['header']
                    print(f"\nAPI Response:")
                    print(f"  - Result Code: {header.get('resultCode')}")
                    print(f"  - Result Message: {header.get('resultMsg')}")

                if 'body' in response_data and 'items' in response_data['body']:
                    items = response_data['body']['items']

                    if 'item' in items:
                        rows = items['item']
                        print(f"\n  - Records fetched: {len(rows)}")

                        print(f"\nSample data (first record):")
                        first = rows[0]
                        for key, value in first.items():
                            print(f"  {key}: {value}")

                        return True
                    else:
                        print("\n[WARNING] No 'item' key in response")
                else:
                    print("\n[WARNING] No data in body")
            else:
                print("\n[ERROR] Unexpected response structure")
                print(f"Response keys: {list(data.keys())}")

            return False

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def get_all_lines_summary():
    """Get summary of all available lines"""
    url = f"{BASE_URL}/1/1000/"  # Get large sample

    try:
        print("\n" + "="*70)
        print("FETCHING COMPLETE LINE SUMMARY")
        print("="*70)

        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=15) as response:
            raw_data = response.read()

            # Handle encoding
            try:
                text_data = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                text_data = raw_data.decode('cp949')

            data = json.loads(text_data)

            if 'response' in data:
                response_data = data['response']

                if 'body' in response_data and 'items' in response_data['body']:
                    items = response_data['body']['items']

                    if 'item' in items:
                        rows = items['item']
                        print(f"\nTotal records fetched: {len(rows)}")

                        # Group by line
                        line_stats = {}
                        for row in rows:
                            line = row.get('lineNm', 'Unknown')
                            if line not in line_stats:
                                line_stats[line] = {
                                    'count': 0,
                                    'stations': set(),
                                    'cars': set(),
                                    'sample': row
                                }
                            line_stats[line]['count'] += 1
                            line_stats[line]['stations'].add(row.get('stnNm', ''))
                            line_stats[line]['cars'].add(row.get('qckgffVhclDoorNo', ''))

                        print(f"\n{'Line':<15} {'Records':<10} {'Stations':<12} {'Car Configs'}")
                        print("-"*70)
                        for line in sorted(line_stats.keys()):
                            stats = line_stats[line]
                            print(f"{line:<15} {stats['count']:<10} {len(stats['stations']):<12} {len(stats['cars'])}")

                        return line_stats
                    else:
                        print("\n[ERROR] No 'item' in response")
                else:
                    print("\n[ERROR] No 'body' or 'items' in response")
            else:
                print("\n[ERROR] No 'response' key")

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def check_line_9_specifically():
    """Check if Line 9 data exists"""
    print("\n" + "="*70)
    print("CHECKING LINE 9 DATA SPECIFICALLY")
    print("="*70)

    # Try to get more records to find Line 9
    url = f"{BASE_URL}/1/2000/"

    try:
        request = urllib.request.Request(url)
        with urllib.request.urlopen(request, timeout=20) as response:
            raw_data = response.read()

            try:
                text_data = raw_data.decode('utf-8')
            except UnicodeDecodeError:
                text_data = raw_data.decode('cp949')

            data = json.loads(text_data)

            if 'response' in data and 'body' in data['response']:
                body = data['response']['body']
                if 'items' in body and 'item' in body['items']:
                    rows = body['items']['item']

                    # Look for Line 9
                    line9_records = [r for r in rows if '9호선' in r.get('lineNm', '') or '9' in r.get('lineNm', '')]

                    if line9_records:
                        print(f"\n[FOUND] Line 9 data EXISTS!")
                        print(f"  - Found {len(line9_records)} records")
                        print(f"\n  Sample Line 9 record:")
                        for key, value in line9_records[0].items():
                            print(f"    {key}: {value}")
                    else:
                        print(f"\n[NOT FOUND] Line 9 data NOT in API")
                        print(f"  - Searched through {len(rows)} records")
                        print(f"  - Available lines: {set(r.get('lineNm') for r in rows[:50])}")

                    return line9_records if line9_records else None

    except Exception as e:
        print(f"\n[ERROR] {str(e)}")
        return None

# Main execution
if __name__ == "__main__":
    print("\n" + "="*70)
    print("SEOUL METRO FAST EXIT API TEST")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-5:]}")
    print("="*70)

    # Step 1: Test basic connection
    if not test_api_connection():
        print("\n[ABORT] API connection failed.")
        exit(1)

    sleep(1)

    # Step 2: Get complete summary
    line_stats = get_all_lines_summary()

    sleep(1)

    # Step 3: Check Line 9 specifically
    line9_data = check_line_9_specifically()

    # Final recommendation
    if line_stats:
        print("\n\n" + "="*70)
        print("RECOMMENDATION FOR METROPY REBUILDING")
        print("="*70)

        # Check if Line 9 has data
        line9_exists = any('9호선' in line or '9' in line for line in line_stats.keys())

        if line9_exists or line9_data:
            print(f"\n[IMPORTANT] Line 9 HAS data in Fast Exit API!")
            print(f"  - This contradicts the original project limitation")
            print(f"  - You CAN use Line 9 for rebuilding!")
        else:
            print(f"\n[IMPORTANT] Line 9 does NOT have data in Fast Exit API")
            print(f"  - This confirms the afterFinal.md statement")
            print(f"  - You should use Lines 1-8 as recommended")

        # Recommend best lines
        print(f"\n[RECOMMENDATION] Top lines for rebuilding:")
        sorted_lines = sorted(line_stats.items(),
                            key=lambda x: x[1]['count'],
                            reverse=True)

        for i, (line, stats) in enumerate(sorted_lines[:5], 1):
            print(f"\n  {i}. {line}")
            print(f"     Records: {stats['count']}")
            print(f"     Unique Stations: {len(stats['stations'])}")
            print(f"     Car Configurations: {len(stats['cars'])}")

            if i == 1:
                print(f"     [BEST CHOICE] Highest data density")

    print("\n\n[DONE] API test complete!")
    print("\nNext steps:")
    print("  1. Choose target line (recommend Line 2 if Line 9 not available)")
    print("  2. Create new directory structure")
    print("  3. Begin data preprocessing pipeline")
