import sys
import json
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point
from concurrent.futures import ThreadPoolExecutor
from google_routing import get_google_route
from here_routing import get_here_route
from osm_routing import get_osm_route

# Default Bounding box for Stuttgart-Weilimdorf
BBOX = (9.10, 48.78, 9.20, 48.88) # min_lon, min_lat, max_lon, max_lat
NUM_ROUTES = 5
BUFFER_METERS = 30 # Buffer size in meters for overlap calculation

# Use a projected CRS for accurate length calculations (UTM zone 32N for Stuttgart)
CRS_PROJ = "EPSG:32632"

def generate_random_points_in_bbox(bbox, num_points):
    """Generate a list of random points within a bounding box."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lons = np.random.uniform(min_lon, max_lon, num_points)
    lats = np.random.uniform(min_lat, max_lat, num_points)
    return list(zip(lons, lats))

def calculate_coverage(base_route_gdf_proj, other_route, buffer_size):
    """Calculates the coverage percentage of other_route on a buffered base_route."""
    if not other_route:
        return 0

    base_length = base_route_gdf_proj.length.sum()
    if base_length == 0:
        return 0

    base_buffered = base_route_gdf_proj.buffer(buffer_size).union_all()
    other_gdf_proj = gpd.GeoDataFrame([{'geometry': other_route}], crs="EPSG:4326").to_crs(CRS_PROJ)
    intersection_length = base_buffered.intersection(other_gdf_proj.union_all()).length
    return (intersection_length / base_length) * 100

def save_gdf_to_geojson(data, filename):
    """Helper function to create and save a GeoDataFrame."""
    if data:
        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326", geometry='geometry')
        gdf.to_file(f"data/{filename}", driver='GeoJSON')

def process_routes(bbox, strategy='shortest'):
    """Fetch and process routes from different providers."""
    print(f"Using Bounding Box: {bbox}")
    print(f"Using Routing Strategy: {strategy}")
    print(f"Generating {NUM_ROUTES} random origin/destination pairs in the given BBOX...")

    # Ensure the origin and destination are not the same
    origins = []
    destinations = []
    while len(origins) < NUM_ROUTES:
        origin, dest = generate_random_points_in_bbox(bbox, 2)
        origins.append(origin)
        destinations.append(dest)

    google_routes = []
    here_routes = []
    osm_routes = []
    od_points = []
    stats = {}

    # --- Define routing options based on strategy ---
    google_opts = {}
    here_opts = {}
    osm_opts = {}

    if strategy == 'shortest':
        here_opts = {'routingMode': 'short'}

    # Use ThreadPoolExecutor to fetch routes concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i in range(NUM_ROUTES):
            origin = origins[i]
            destination = destinations[i]
            print(f"Processing route {i+1}/{NUM_ROUTES} from {origin} to {destination}...")

            od_points.append({'geometry': Point(origin), 'pair_id': i, 'type': 'origin'})
            od_points.append({'geometry': Point(destination), 'pair_id': i, 'type': 'destination'})

            # Submit all routing requests concurrently
            future_google = executor.submit(get_google_route, origin, destination, google_opts)
            future_here = executor.submit(get_here_route, origin, destination, here_opts)
            future_osm = executor.submit(get_osm_route, origin, destination, osm_opts)

            # Get results
            google_route, google_details = future_google.result()
            here_route, here_details = future_here.result()
            osm_route, osm_details = future_osm.result()

            if google_route:
                google_routes.append({
                    'geometry': google_route, 'route_id': i, 
                    'distance': google_details.get('distance'), 'duration': google_details.get('duration'),
                    'instructions': json.dumps(google_details.get('instructions', [])) # GeoJSON properties work best with simple types or JSON strings
                })
            if here_route:
                here_routes.append({
                    'geometry': here_route, 'route_id': i,
                    'distance': here_details.get('distance'), 'duration': here_details.get('duration'),
                    'instructions': json.dumps(here_details.get('instructions', []))
                })
            if osm_route:
                osm_routes.append({
                    'geometry': osm_route, 'route_id': i,
                    'distance': osm_details.get('distance'), 'duration': osm_details.get('duration'),
                    'instructions': json.dumps(osm_details.get('instructions', []))
                })

            # Calculate overlap stats if Google route exists
            if google_route:
                google_gdf_proj = gpd.GeoDataFrame([{'geometry': google_route}], crs="EPSG:4326").to_crs(CRS_PROJ)
                here_coverage = calculate_coverage(google_gdf_proj, here_route, BUFFER_METERS)
                osm_coverage = calculate_coverage(google_gdf_proj, osm_route, BUFFER_METERS)
                
                stats[i] = {
                    "here_coverage": f"{here_coverage:.2f}%",
                    "osm_coverage": f"{osm_coverage:.2f}%",
                    "google_details": google_details,
                    # Add details for other providers if they exist
                    "here_details": here_details if here_details else {},
                    "osm_details": osm_details if osm_details else {}
                }

    return google_routes, here_routes, osm_routes, od_points, stats

if __name__ == '__main__':
    import os
    if not os.path.exists('data'):
        os.makedirs('data')

    # Check for command-line arguments for BBOX
    if len(sys.argv) >= 5:
        try:
            current_bbox = tuple(map(float, sys.argv[1:5]))
        except ValueError:
            print("Invalid BBOX arguments. Using default.")
            current_bbox = BBOX
        # The 6th argument is the strategy
        strategy = sys.argv[5] if len(sys.argv) > 5 else 'shortest'
    else:
        current_bbox = BBOX
        strategy = 'shortest'

    google_routes, here_routes, osm_routes, od_points, stats = process_routes(current_bbox, strategy)

    # Save routes to GeoJSON files
    save_gdf_to_geojson(google_routes, "google_routes.geojson")
    save_gdf_to_geojson(here_routes, "here_routes.geojson")
    save_gdf_to_geojson(osm_routes, "osm_routes.geojson")
    
    if od_points: # Keep this separate as it has a different structure
        od_gdf = gpd.GeoDataFrame(od_points, crs="EPSG:4326", geometry='geometry')
        od_gdf.to_file("data/od_points.geojson", driver='GeoJSON')

    with open("data/stats.json", "w") as f:
        json.dump(stats, f)

    print("Route processing complete.")