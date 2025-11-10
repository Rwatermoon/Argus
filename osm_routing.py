import requests
import polyline
from shapely.geometry import LineString
import os
import json
from datetime import datetime, timezone
import pytz
import logging

logger = logging.getLogger(__name__)

OSRM_ENDPOINT = "http://router.project-osrm.org/route/v1/driving/"
GRAPHHOPPER_ENDPOINT = "https://graphhopper.com/api/1/route"
USAGE_FILE = 'graphhopper_usage.json'

def _update_gh_usage():
    """Increments the GraphHopper API usage count for the current day."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    usage = {'date': today, 'count': 0}
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            if data.get('date') == today:
                usage = data
        except (json.JSONDecodeError, IOError):
            # If file is corrupted or unreadable, start fresh
            pass
    
    usage['count'] += 1
    
    with open(USAGE_FILE, 'w') as f:
        json.dump(usage, f)

def get_graphhopper_usage():
    """Gets the GraphHopper API usage count for the current day."""
    today = datetime.utcnow().strftime('%Y-%m-%d')
    if not os.path.exists(USAGE_FILE):
        return 0
    try:
        with open(USAGE_FILE, 'r') as f:
            data = json.load(f)
        if data.get('date') == today:
            return data.get('count', 0)
    except (json.JSONDecodeError, IOError):
        pass
    return 0

def get_graphhopper_route(origin, destination, routing_options=None):
    """
    Get a route from GraphHopper API.
    """
    logger.debug(f"get_graphhopper_route called with origin: {origin}, destination: {destination}")
    api_key = os.getenv("GRAPHHOPPER_API_KEY")

    if not api_key:
        logger.error("GRAPHHOPPER_API_KEY not set.")
        return None, None

    if routing_options is None:
        routing_options = {}

    # Map our strategy to GraphHopper's 'weighting' parameter
    strategy = routing_options.pop('strategy', 'fastest') # Pop to avoid sending it as a query param
    weighting = 'fastest' if strategy == 'fastest' else 'shortest'

    params = {
        'vehicle': 'car',
        'instructions': 'true',
        'points_encoded': 'true',
        'key': api_key,
        'weighting': weighting,
        **routing_options
    }
    # Manually add point parameters to ensure correct formatting
    params['point'] = [f'{origin[1]},{origin[0]}', f'{destination[1]},{destination[0]}']

    try:
        # Use requests' ability to handle lists of parameters correctly
        response = requests.get(GRAPHHOPPER_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        _update_gh_usage() # Increment usage count on successful API call
        data = response.json()

        if 'paths' in data and data['paths']:
            path = data['paths'][0]
            # GraphHopper uses the same polyline encoding
            decoded_geom = polyline.decode(path['points'])
            line = LineString([(lon, lat) for lat, lon in decoded_geom])

            instructions = [item['text'] for item in path.get('instructions', [])]
            
            details = {
                'distance': path['distance'], # meters
                'duration': path['time'] / 1000, # ms to seconds
                'instructions': instructions
            }
            return line, details
        else:
            logger.warning(f"GraphHopper API returned no route. Response: {data}")
            return None, None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching GraphHopper route: {e}")
        return None, None

def get_osm_route(origin, destination, routing_options=None):
    """
    Get a route from OSRM API.
    """
    logger.debug(f"get_osm_route called with origin: {origin}, destination: {destination}")
    if routing_options is None:
        routing_options = {}

    # OSRM doesn't support a 'strategy' parameter, so we remove it if it exists.
    routing_options.pop('strategy', None)

    # OSRM expects coordinates as lon,lat
    origin_str = f'{origin[0]},{origin[1]}'
    destination_str = f'{destination[0]},{destination[1]}'
    
    base_url = f'{OSRM_ENDPOINT}{origin_str};{destination_str}'
    params = {'overview': 'full', 'geometries': 'polyline', 'steps': 'true', 'annotations': 'true', **routing_options}
    param_string = '&'.join([f'{k}={v}' for k, v in params.items()])

    try:
        response = requests.get(f"{base_url}?{param_string}")
        response.raise_for_status()
        data = response.json()

        if 'routes' in data and data['routes']:
            route = data['routes'][0]
            geom = route['geometry']
            # OSRM uses polyline encoding with 5 decimal places precision
            decoded_geom = polyline.decode(geom)
            # The decoded geometry is a list of (lat, lon) tuples
            # Convert it to (lon, lat) for shapely
            line = LineString([(lon, lat) for lat, lon in decoded_geom])
            
            instructions = []
            for leg in route.get('legs', []):
                for step in leg.get('steps', []):
                    maneuver = step.get('maneuver', {})
                    step_type = maneuver.get('type', '')
                    modifier = maneuver.get('modifier', '')
                    street_name = step.get('name', '')

                    # Construct a human-readable instruction
                    if step_type == 'depart':
                        instruction = f"Head on {street_name}"
                    else:
                        instruction = f"{step_type.replace('_', ' ').title()} {modifier} onto {street_name}".strip()
                    instructions.append(instruction)

            details = {'distance': route['distance'], 'duration': route['duration'], 'instructions': list(dict.fromkeys(instructions))} # Remove duplicates
            return line, details
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching OSRM route: {e}")
        return None, None
