import os
import requests
import flexpolyline
from shapely.geometry import LineString
from dotenv import load_dotenv

load_dotenv()

HERE_API_KEY = os.getenv("HERE_MAP_DATA_API_KEY")
HERE_ROUTING_ENDPOINT = "https://router.hereapi.com/v8/routes"

def get_here_route(origin, destination, routing_options=None):
    """
    Get a route from HERE Routing API v8.
    """
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
        print(f"Error fetching HERE route: {e}")
        return None, None # Explicitly return a tuple of Nones
