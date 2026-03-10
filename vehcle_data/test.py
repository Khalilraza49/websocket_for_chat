import requests
import pandas as pd
from time import sleep
import json
from tqdm import tqdm

BASE_URL = "https://www.carqueryapi.com/api/0.3/"
HEADERS = {'User-Agent': 'Mozilla/5.0'}
OUTPUT_FILE = "car_trims_1975_2025.csv"
START_YEAR = 1975
END_YEAR = 1976
DELAY = 1  # seconds between requests

def get_trims(year):
    """Fetch trim data for a specific year"""
    url = f"{BASE_URL}?cmd=getTrims&year={year}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            # Handle JSONP response
            if response.text.startswith('?(') and response.text.endswith(')'):
                json_str = response.text[2:-1]
                data = json.loads(json_str)
                if 'Trims' in data:
                    # Add year to each trim record
                    for trim in data['Trims']:
                        trim['year'] = year
                    return {
                        'trims': data['Trims'],
                        'count': len(data['Trims'])
                    }
        return {'trims': [], 'count': 0}
    except Exception as e:
        print(f"Error fetching year {year}: {e}")
        return {'trims': [], 'count': 0}

def main():
    all_trims = []
    year_counts = {}
    
    # Initialize progress bar
    pbar = tqdm(range(START_YEAR, END_YEAR + 1), desc="Fetching data")
    
    for year in pbar:
        pbar.set_description(f"Fetching year {year}")
        result = get_trims(year)
        if result['trims']:
            all_trims.extend(result['trims'])
            year_counts[year] = result['count']
            pbar.set_postfix({
                'Current Year Count': result['count'],
                'Total Trims': len(all_trims)
            })
        sleep(DELAY)  # Be polite to the API
    
    if all_trims:
        # Convert to DataFrame and save as CSV
        df = pd.DataFrame(all_trims)
        df.to_csv(OUTPUT_FILE, index=False)
        
        # Print year-wise counts
        print("\nYear-wise Trim Counts:")
        for year in sorted(year_counts.keys()):
            print(f"{year}: {year_counts[year]} trims")
        
        print(f"\nSuccess! Saved {len(df)} total records to {OUTPUT_FILE}")
    else:
        print("\nNo data was collected.")

if __name__ == "__main__":
    main()
