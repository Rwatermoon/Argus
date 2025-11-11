import os
import requests
import flexpolyline
from shapely.geometry import LineString
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger(__name__)

HERE_API_KEY = os.getenv("HERE_MAP_DATA_API_KEY")
HERE_ROUTING_ENDPOINT = "https://router.hereapi.com/v8/routes"
HERE_REVGEOCODE_ENDPOINT = "https://revgeocode.search.hereapi.com/v1/revgeocode"

def get_here_route(origin, destination, routing_options=None):
    """
    Get a route from HERE Routing API v8.
    """
    if not HERE_API_KEY:
        logger.error("HERE_API_KEY not set. Cannot fetch HERE route.")
        return None, None
    if routing_options is None:
        routing_options = {}

    params = {
        'transportMode': 'car',
        'origin': f'{origin[1]},{origin[0]}',
        'destination': f'{destination[1]},{destination[0]}',
        'return': 'polyline,summary,actions,instructions',
        'apiKey': HERE_API_KEY,
        **routing_options
    }

    try:
        response = requests.get(HERE_ROUTING_ENDPOINT, params=params)
        response.raise_for_status()
        data = response.json()

        if 'routes' in data and data['routes']:
            route = data['routes'][0]
            
            # Combine polylines and summaries from all sections
            full_polyline = []
            total_length = 0
            total_duration = 0
            instructions = []
            for section in route['sections']:
                decoded_section = flexpolyline.decode(section['polyline'])
                full_polyline.extend(decoded_section)
                total_length += section['summary']['length']
                total_duration += section['summary']['duration']
                # Extract street names from actions
                for action in section.get('actions', []):
                    instruction = action.get('instruction', '')
                    if instruction:
                        instructions.append(instruction)

            # The decoded polyline is a list of (lat, lon) tuples
            # Convert it to (lon, lat) for shapely
            line = LineString([(lon, lat) for lat, lon in full_polyline])
            details = {'distance': total_length, 'duration': total_duration, 'instructions': list(dict.fromkeys(instructions))} # Remove duplicates
            return line, details
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching HERE route: {e}")
        return None, None # Explicitly return a tuple of Nones

def snap_to_road_here(point):
    """
    Snaps a single point (lon, lat) to the nearest road using the HERE Reverse Geocode API.
    Returns the snapped (lon, lat) tuple, or the original point if snapping fails.
    """
    if not HERE_API_KEY:
        logger.error("HERE_API_KEY not set, cannot snap to road.")
        return point

    lon, lat = point
    params = {
        'at': f'{lat},{lon}',
        'lang': 'en-US',
        'apiKey': HERE_API_KEY
    }

    try:
        response = requests.get(HERE_REVGEOCODE_ENDPOINT, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        if data.get('items') and data['items'][0].get('position'):
            snapped_pos = data['items'][0]['position']
            return (snapped_pos['lng'], snapped_pos['lat'])
    except requests.exceptions.RequestException as e:
        logger.warning(f"Could not snap point {point} with HERE API: {e}. Using original point.")
    
    return point # Fallback to original point
