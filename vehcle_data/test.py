
import requests
import pandas as pd
from tqdm import tqdm
import time
import json
import re
import os

BASE_URL = "https://www.carqueryapi.com/api/0.3/"
HEADERS = {'User-Agent': 'Mozilla/5.0'}
CSV_PATH = "vehicle_full_data.csv"

# Extract JSON from JSONP
def parse_jsonp(jsonp):
    try:
        match = re.search(r'\?\((\{.*\})\);?', jsonp)
        if match:
            return json.loads(match.group(1))
        elif jsonp.strip().startswith("{"):
            return json.loads(jsonp)
        else:
            raise ValueError("No valid JSON found")
    except Exception as e:
        print("Parsing error:", e)
        return {}

# Get trims for one year
def get_trims_by_year(year):
    params = {
        'cmd': 'getTrims',
        'year': year,
        'sold_in_us': 1
    }
    try:
        res = requests.get(BASE_URL, params=params, headers=HEADERS)
        if res.status_code != 200 or not res.text:
            print(f"❌ Failed to get trims for {year}")
            return []
        return parse_jsonp(res.text).get("Trims", [])
    except Exception as e:
        print(f"⚠️ Error fetching trims for {year}: {e}")
        return []

# Load previous data if exists
def load_existing_data():
    if os.path.exists(CSV_PATH):
        print(f"🔁 Loading existing data from {CSV_PATH}")
        return pd.read_csv(CSV_PATH)
    return pd.DataFrame()

# Main function
def main():
    existing_df = load_existing_data()
    all_data = existing_df.to_dict("records")
    processed_years = set(existing_df["model_year"].unique()) if "model_year" in existing_df else set()

    years = range(1975, 2026)

    for year in tqdm(years, desc="Processing Years"):
        if str(year) in processed_years:
            print(f"⏩ Skipping already-processed year: {year}")
            continue

        try:
            trims = get_trims_by_year(year)
            all_data.extend(trims)

            # Save immediately
            df = pd.DataFrame(all_data)
            df.to_csv(CSV_PATH, index=False)
            print(f"✅ Year {year} saved ({len(trims)} rows added)")
            time.sleep(0.2)

        except Exception as e:
            print(f"❗ Error during year {year}: {e}")
            # Save partial progress anyway
            df = pd.DataFrame(all_data)
            df.to_csv(CSV_PATH, index=False)
            print("📝 Partial data saved before exiting.")
            break

    print(f"\n📦 Final saved file: {CSV_PATH} ({len(all_data)} rows)")

if __name__ == "__main__":
    main()

