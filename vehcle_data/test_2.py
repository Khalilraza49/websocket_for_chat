import requests
import pandas as pd
from time import sleep
import sys
# Function to make API calls with error handling
def call_api(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        # The API returns JSONP, so we need to strip the callback wrapper
        json_data = response.text
        json_data = json_data[json_data.index('(')+1:json_data.rindex(')')]
        return eval(json_data)
    except Exception as e:
        print(f"Error calling API: {url} - {str(e)}")
        return None

# Main function to collect all data
def collect_car_data():
    all_trims = []
    
    for year in range(1975, 1976):
        print(f"Processing year: {year}")
        
        # First API call - get all makes for the year
        makes_url = f"https://www.carqueryapi.com/api/0.3/?callback=?&cmd=getMakes&year={year}&sold_in_us=1"
        makes_data = call_api(makes_url)
        print(f"  Found makes: {len(makes_data['Makes']) if makes_data and 'Makes' in makes_data else 0}")
        sys.exit(0)  
        if not makes_data or 'Makes' not in makes_data:
            print(f"No makes found for year {year}")
            continue
        
        for make in makes_data['Makes']:
            print(f"  Processing make: {make['make_name']}")
            make_id = make['make_id']
            print(f"  Processing make: {make_id}")
            
            # Second API call - get all models for the make and year
            models_url = f"https://www.carqueryapi.com/api/0.3/?callback=?&cmd=getModels&make={make_id}&year={year}&sold_in_us=1"
            models_data = call_api(models_url)
            
            if not models_data or 'Models' not in models_data:
                print(f"    No models found for make {make_id} in year {year}")
                continue
            
            for model in models_data['Models']:
                model_name = model['model_name']
                print(f"      Processing model: {model_name}")
                
                # Third API call - get all trims for the make, model, and year
                trims_url = f"https://www.carqueryapi.com/api/0.3/?callback=?&cmd=getTrims&make={make_id}&model={model_name}&year={year}"
                trims_data = call_api(trims_url)
                
                if not trims_data or 'Trims' not in trims_data:
                    print(f"        No trims found for model {model_name} of make {make_id} in year {year}")
                    continue
                
                # Add year, make, and model info to each trim record
                for trim in trims_data['Trims']:
                    trim['year'] = year
                    trim['make'] = make_id
                    trim['model'] = model_name
                    all_trims.append(trim)
                
                # Be polite with API calls
                sleep(0.1)
    
    return all_trims

# Collect all data
car_data = collect_car_data()

# Convert to DataFrame and save as CSV
if car_data:
    df = pd.DataFrame(car_data)
    df.to_csv('car_trims_1975_2025.csv', index=False)
    print(f"Data saved to car_trims_1975_2025.csv with {len(df)} records.")
else:
    print("No data was collected.")
