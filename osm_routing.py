import requests
import polyline
from shapely.geometry import LineString

OSRM_ENDPOINT = "http://router.project-osrm.org/route/v1/driving/"

def get_osm_route(origin, destination, routing_options=None):
    """
    Get a route from OSRM API.
    """
    if routing_options is None:
        routing_options = {}

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
        print(f"Error fetching OSRM route: {e}")
        return None, None
