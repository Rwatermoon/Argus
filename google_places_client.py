import os
import requests
import logging

logger = logging.getLogger(__name__)

# Use the same key as Directions/Roads API for simplicity
GOOGLE_API_KEY = os.getenv("GOOGLE_ROADS_API_KEY")
PLACES_API_ENDPOINT = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

def search_pois_in_bbox(bbox, limit=20):
    """
    Searches for POIs within a given bounding box using the Google Places API.
    bbox is (min_lon, min_lat, max_lon, max_lat).
    """
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_ROADS_API_KEY not set. Cannot fetch Google Places POIs.")
        return []

    # Google Places API 'nearbysearch' works with a center point and a radius.
    # We'll calculate the center and radius from the bbox.
    center_lon = (bbox[0] + bbox[2]) / 2
    center_lat = (bbox[1] + bbox[3]) / 2
    
    # Calculate radius (diagonal distance / 2) in meters
    from data_processing import haversine_distance
    radius_km = haversine_distance((bbox[0], bbox[1]), (bbox[2], bbox[3])) / 2
    radius_meters = radius_km * 1000

    params = {
        "location": f"{center_lat},{center_lon}",
        "radius": radius_meters,
        "key": GOOGLE_API_KEY
    }

    try:
        response = requests.get(PLACES_API_ENDPOINT, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Google Places API returned {len(data.get('results', []))} POIs.")
        return data.get('results', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Google Places POIs: {e}")
        return []