import sys
import json
import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, Point
from concurrent.futures import ThreadPoolExecutor
from google_routing import get_google_route
from here_routing import get_here_route
from osm_routing import get_osm_route, get_graphhopper_route, snap_to_road_osrm
from logger_config import setup_logger
import logging

# Default Bounding box for Stuttgart-Weilimdorf
BBOX = (9.10, 48.78, 9.20, 48.88) # min_lon, min_lat, max_lon, max_lat
NUM_ROUTES = 5
BUFFER_METERS = 30 # Buffer size in meters for overlap calculation

# Use a projected CRS for accurate length calculations (UTM zone 32N for Stuttgart)
CRS_PROJ = "EPSG:32632"

# Setup logger
setup_logger()

# Custom JSON encoder to handle GeoDataFrame
# Moved to the top level to be accessible on import.
class GeoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, gpd.GeoDataFrame):
            return json.loads(obj.to_json())
        return json.JSONEncoder.default(self, obj)

def generate_random_points_in_bbox(bbox, num_points):
    """Generate a list of random points within a bounding box."""
    min_lon, min_lat, max_lon, max_lat = bbox
    lons = np.random.uniform(min_lon, max_lon, num_points)
    lats = np.random.uniform(min_lat, max_lat, num_points)
    return list(zip(lons, lats))

def log_progress(current, total, message):
    """Logs progress as a JSON object for the frontend to parse."""
    progress_percentage = int((current / total) * 100)
    # Use a specific format that the frontend can distinguish from regular logs
    progress_log = {"type": "progress", "progress": progress_percentage, "message": message}
    # Print directly to stdout to ensure it's always sent, regardless of log level
    print(json.dumps(progress_log))
    sys.stdout.flush()

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
    full_path = f"data/{filename}"
    if data:
        gdf = gpd.GeoDataFrame(data, crs="EPSG:4326", geometry='geometry')
        gdf.to_file(full_path, driver='GeoJSON')
    else:
        # If there's no data, create an empty GeoJSON file to overwrite the old one.
        empty_geojson = {"type": "FeatureCollection", "features": []}
        with open(full_path, 'w') as f:
            json.dump(empty_geojson, f)

def calculate_single_route_comparison(origin, destination, strategy, osm_provider):
    """
    Fetches and processes a single route from all providers for a given OD pair.
    Returns GeoJSON FeatureCollections and stats for one route.
    """
    logging.debug(f"Calculating single route. O: {origin}, D: {destination}, Strategy: {strategy}, Provider: {osm_provider}")
    google_routes, here_routes, osm_routes = [], [], []
    stats = {}

    # --- Define routing options based on strategy ---
    here_opts = {}
    google_opts = {'strategy': strategy}
    osm_opts = {'strategy': strategy}
    if strategy == 'shortest':
        here_opts = {'routingMode': 'short'}

    with ThreadPoolExecutor(max_workers=3) as executor:
        logging.debug("Submitting routing tasks to thread pool...")
        future_google = executor.submit(get_google_route, origin, destination, google_opts)
        future_here = executor.submit(get_here_route, origin, destination, here_opts)
        if osm_provider == 'graphhopper':
            future_osm = executor.submit(get_graphhopper_route, origin, destination, osm_opts)
        else:
            future_osm = executor.submit(get_osm_route, origin, destination, osm_opts)

        logging.debug("Waiting for routing tasks to complete...")
        google_route, google_details = future_google.result()
        here_route, here_details = future_here.result()
        osm_route, osm_details = future_osm.result()
        logging.debug(f"Google result: {'OK' if google_route else 'None'}. HERE result: {'OK' if here_route else 'None'}. OSM result: {'OK' if osm_route else 'None'}.")

    # --- Process results ---
    logging.debug("Processing API results...")
    if google_route:
        google_routes.append({'geometry': google_route, 'route_id': 0, **google_details})
    if here_route:
        here_routes.append({'geometry': here_route, 'route_id': 0, **here_details})
    if osm_route:
        osm_routes.append({'geometry': osm_route, 'route_id': 0, **osm_details})

    # --- Calculate stats ---
    if google_route:
        google_gdf_proj = gpd.GeoDataFrame([{'geometry': google_route}], crs="EPSG:4326").to_crs(CRS_PROJ)
        here_coverage = calculate_coverage(google_gdf_proj, here_route, BUFFER_METERS)
        osm_coverage = calculate_coverage(google_gdf_proj, osm_route, BUFFER_METERS)
        stats[0] = {
            "here_coverage": f"{here_coverage:.2f}%",
            "osm_coverage": f"{osm_coverage:.2f}%",
            "google_details": google_details,
            "here_details": here_details if here_details else {},
            "osm_details": osm_details if osm_details else {}
        }

    final_results = {
        "google_routes": gpd.GeoDataFrame(google_routes, crs="EPSG:4326", geometry='geometry'),
        "here_routes": gpd.GeoDataFrame(here_routes, crs="EPSG:4326", geometry='geometry'),
        "osm_routes": gpd.GeoDataFrame(osm_routes, crs="EPSG:4326", geometry='geometry'),
        "stats": stats
    }
    logging.debug("Finished calculating single route comparison.")
    return final_results

def process_routes(bbox, strategy='shortest', osm_provider='osrm'):
    """Fetch and process routes from different providers."""
    # Total steps: 1 for setup, NUM_ROUTES for processing, 1 for saving
    total_steps = NUM_ROUTES + 2

    log_progress(0, total_steps, f"Initializing... Strategy: {strategy}, OSM Provider: {osm_provider}")

    # Step 1: Generate points
    log_progress(1, total_steps, f"Generating {NUM_ROUTES} random origin/destination pairs...")

    # Ensure the origin and destination are not the same
    origins = []
    destinations = []
    while len(origins) < NUM_ROUTES:
        # Generate a random origin and destination
        raw_origin, raw_dest = generate_random_points_in_bbox(bbox, 2)
        # Snap them to the nearest road to ensure they are routable
        origin = snap_to_road_osrm(raw_origin)
        dest = snap_to_road_osrm(raw_dest)
        origins.append(origin)
        destinations.append(dest)

    google_routes = []
    here_routes = []
    osm_routes = []
    od_points = []
    stats = {}

    # --- Define routing options based on strategy ---
    here_opts = {}
    # Pass the strategy to the providers that support it
    google_opts = {'strategy': strategy}
    osm_opts = {'strategy': strategy}

    if strategy == 'shortest':
        here_opts = {'routingMode': 'short'}

    # Use ThreadPoolExecutor to fetch routes concurrently
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i in range(NUM_ROUTES):
            origin = origins[i]
            destination = destinations[i]
            # Step 1 (generation) + i+1 (current route)
            log_progress(i + 2, total_steps, f"Fetching route {i+1}/{NUM_ROUTES}...")

            od_points.append({'geometry': Point(origin), 'pair_id': i, 'type': 'origin'})
            od_points.append({'geometry': Point(destination), 'pair_id': i, 'type': 'destination'})

            # Submit all routing requests concurrently
            future_google = executor.submit(get_google_route, origin, destination, google_opts)
            future_here = executor.submit(get_here_route, origin, destination, here_opts)
            
            # Choose OSM provider based on the parameter
            if osm_provider == 'graphhopper':
                future_osm = executor.submit(get_graphhopper_route, origin, destination, osm_opts)
            else: # Default to OSRM
                future_osm = executor.submit(get_osm_route, origin, destination, osm_opts)

            # Get results
            google_route, google_details = future_google.result()
            here_route, here_details = future_here.result()
            osm_route, osm_details = future_osm.result()

            if google_route:
                google_routes.append({
                    'geometry': google_route, 'route_id': i, 
                    'distance': google_details.get('distance'), 'duration': google_details.get('duration'),
                    'instructions': json.dumps(google_details.get('instructions', []))
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
                    "here_details": here_details if here_details else {},
                    "osm_details": osm_details if osm_details else {}
                }

    log_progress(total_steps, total_steps, "Saving results...")

    return google_routes, here_routes, osm_routes, od_points, stats

if __name__ == '__main__':
    import os
    logging.debug(f"data_processing.py script started with args: {sys.argv}")

    if not os.path.exists('data'):
        os.makedirs('data')

    # Mode 1: Random (7 args: script, lon1, lat1, lon2, lat2, strategy, osm_provider)
    if len(sys.argv) == 7:
        logging.info("Running in RANDOM mode.")
        try:
            current_bbox = tuple(map(float, sys.argv[1:5]))
        except ValueError:
            logging.error("Invalid BBOX arguments. Using default.")
            current_bbox = BBOX
        strategy = sys.argv[5]
        osm_provider = sys.argv[6]
        google_routes, here_routes, osm_routes, od_points, stats = process_routes(current_bbox, strategy, osm_provider)
        
        # Save all results for random mode
        save_gdf_to_geojson(google_routes, "google_routes.geojson")
        save_gdf_to_geojson(here_routes, "here_routes.geojson")
        save_gdf_to_geojson(osm_routes, "osm_routes.geojson")
        if od_points:
            od_gdf = gpd.GeoDataFrame(od_points, crs="EPSG:4326", geometry='geometry')
            od_gdf.to_file("data/od_points.geojson", driver='GeoJSON')
        with open("data/stats.json", "w") as f:
            json.dump(stats, f, cls=GeoJSONEncoder)

        log_progress(100, 100, "Comparison complete! You can now view the results.")

    # Mode 2: Manual (8 args: script, --manual, olon, olat, dlon, dlat, strategy, osm_provider)
    elif len(sys.argv) == 8 and sys.argv[1] == '--manual':
        logging.info("Running in MANUAL mode.")
        origin = (float(sys.argv[2]), float(sys.argv[3]))
        destination = (float(sys.argv[4]), float(sys.argv[5]))
        strategy = sys.argv[6]
        osm_provider = sys.argv[7]
        results = calculate_single_route_comparison(origin, destination, strategy, osm_provider)
        
        log_progress(100, 100, "Manual calculation complete!")
        logging.debug(f"Sending manual_result to frontend. OSM routes count: {len(results['osm_routes'])}")
        print(json.dumps({"type": "manual_result", "data": results}, cls=GeoJSONEncoder, separators=(',', ':')), flush=True)

    else:
        logging.error(f"Invalid arguments. Received {len(sys.argv)} arguments: {sys.argv}")
        sys.exit(1)