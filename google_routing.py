import os
import googlemaps
from shapely.geometry import LineString
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_ROADS_API_KEY") # Using the same key as before
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

def get_google_route(origin, destination, routing_options=None):
    """
    Get a route from Google Directions API.
    """
    if routing_options is None:
        routing_options = {}
        
    # Pop the strategy to use it for logic, not as a query param
    strategy = routing_options.pop('strategy', 'fastest')

    try:
        # Request alternative routes from the API
        directions_result = gmaps.directions(
            (origin[1], origin[0]),
            (destination[1], destination[0]),
            mode="driving",
            alternatives=True,
            **routing_options
        )

        # print(f"Google API response: {directions_result}") # This can be very verbose

        if directions_result:
            best_route = None
            
            if strategy == 'shortest':
                # Find the route with the minimum distance
                best_route = min(directions_result, key=lambda r: r['legs'][0]['distance']['value'])
            else: # 'fastest' or default
                # Find the route with the minimum duration
                best_route = min(directions_result, key=lambda r: r['legs'][0]['duration']['value'])

            route = best_route
            polyline = route['overview_polyline']['points']
            decoded_polyline = googlemaps.convert.decode_polyline(polyline)
            # The decoded polyline is a list of dicts {'lat': ..., 'lng': ...}
            # Convert it to a list of (lon, lat) tuples for shapely
            line = LineString([(point['lng'], point['lat']) for point in decoded_polyline])
            
            # Extract summary info (distance in meters, duration in seconds)
            leg = route['legs'][0]
            
            # Extract street names from steps
            instructions = []
            import re
            for step in leg.get('steps', []):
                # The html_instructions are the most reliable source for street names
                instruction = step.get('html_instructions', '')
                # Remove HTML tags and extract content
                plain_text = re.sub('<[^<]+?>', ' ', instruction).strip()
                if plain_text:
                    instructions.append(plain_text)

            details = {
                'distance': leg['distance']['value'], 
                'duration': leg['duration']['value'],
                'instructions': list(dict.fromkeys(instructions)) # Remove duplicates
            }
            
            return line, details
        else:
            print("Google API returned no route.")
            return None, None
    except googlemaps.exceptions.ApiError as e:
        print(f"Google API Error: {e}")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred with Google API: {e}")
        return None, None
