import requests
import os
from dotenv import load_dotenv

load_dotenv()

#Set up authentication details
API_KEY = os.getenv("HEVY_API_KEY")
print("API key loaded:", bool(API_KEY))

URL = "https://api.hevyapp.com/v1/workouts"

#Build headers matching Hevy's expectations
headers = {
    "api-key": API_KEY,
    "Accept": "application/json"
}

# Add optional pagination parameters
params = {
    "page": 1,
    "pageSize": 10
}

try:
    response = requests.get(URL, headers=headers, params=params, timeout=10)
    
    response.raise_for_status()
    
    workout_data = response.json()
    print("Successfully retrieved workout data!")
    print(workout_data)
    
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occured: {http_err}")
    if response.status_code == 401:
        print("Tip: Double check you API key or Hevy Pro Status")
    
except requests.exceptions.RequestException as err:
    print(f"An error ocurred: {err}")