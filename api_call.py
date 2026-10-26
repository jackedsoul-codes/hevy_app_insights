import requests
import os
from dotenv import load_dotenv
import time
import json

load_dotenv()

#Set up authentication details
API_KEY = os.getenv("HEVY_API_KEY")
print("API key loaded:", bool(API_KEY))
PATH = "https://api.hevyapp.com/"
URL = f"{PATH}v1/workouts"

#variables

all_workouts = []
current_page = 1
max_page_size = 10

#Build headers matching Hevy's expectations
headers = {
    "api-key": API_KEY,
    "Accept": "application/json"
}

# Add optional pagination parameters
params = {
    "page": current_page,
    "pageSize": max_page_size
}

while True:
    
    try:
        response = requests.get(URL, headers=headers, params=params, timeout=10)
        
        response.raise_for_status()
        
        workout_data = response.json()
        print("Successfully retrieved workout data!")
        # print(workout_data)
        
        # Extract the workouts array from this page
        workout_on_page = workout_data.get("workouts",[])
        if not workout_on_page:
            break # Stop if an empty list is returned
        
        all_workouts.extend(workout_on_page)
        print(
            f"Fetched page {current_page} of {workout_data.get('page_count')} "
            f"({len(workout_on_page)} workouts)"
        )
        
        # Stop loop if we reached the final page reported by the API
        if current_page >= workout_data.get("page_count", 1):
            break
        
        current_page += 1

        # Defensive pause to respect API rate limits
        time.sleep(0.5)
        
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occured: {http_err}")
        if response.status_code == 401:
            print("Tip: Double check you API key or Hevy Pro Status")
            break
        
    except requests.exceptions.RequestException as err:
        print(f"An error ocurred: {err}")
        break
        
print(f"\nFinished! Total workouts retrieved: {len(all_workouts)}")

with open("workouts_raw.json", "w") as file:
    json.dump(all_workouts, file, indent=4)
    
print("Workout data saved successfully")