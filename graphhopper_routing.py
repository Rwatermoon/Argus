import os
import requests
import json
from datetime import date

def get_api_key():
    return os.environ.get('GRAPHHOPPER_API_KEY')

def get_usage_count():
    try:
        with open('data/graphhopper_usage.json', 'r') as f:
            usage_data = json.load(f)
            today = str(date.today())
            if usage_data.get('date') == today:
                return usage_data.get('count', 0)
            else:
                return 0
    except (FileNotFoundError, json.JSONDecodeError):
        return 0

def increment_usage_count():
    count = get_usage_count()
    today = str(date.today())
    usage_data = {'date': today, 'count': count + 1}
    with open('data/graphhopper_usage.json', 'w') as f:
        json.dump(usage_data, f)

def calculate_route(start_point, end_point, mode):
    api_key = get_api_key()
    if not api_key:
        raise ValueError("GraphHopper API key not found.")

    profile = 'car'
    optimization = 'fastest' if mode == 'fastest' else 'shortest'

    url = f"https://graphhopper.com/api/1/route"
    params = {
        'point': [f"{start_point[1]},{start_point[0]}", f"{end_point[1]},{end_point[0]}"],
        'profile': profile,
        'optimization': optimization,
        'calc_points': 'true',
        'points_encoded': 'false',
        'key': api_key,
        'type': 'json'
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        increment_usage_count()
        data = response.json()
        
        if 'paths' not in data or not data['paths']:
            return None

        path = data['paths'][0]
        coordinates = [[coord[0], coord[1]] for coord in path['points']['coordinates']]
        
        route_geojson = {
            'type': 'Feature',
            'properties': {
                'distance': path['distance'],
                'time': path['time'] / 1000  # Convert ms to s
            },
            'geometry': {
                'type': 'LineString',
                'coordinates': coordinates
            }
        }
        return route_geojson

    except requests.exceptions.RequestException as e:
        print(f"Error calling GraphHopper API: {e}")
        return None
