import os
import requests
import logging

logger = logging.getLogger(__name__)

FSQ_API_KEY = os.getenv("FOURSQUARE_API_KEY")
FSQ_PLACES_ENDPOINT = "https://api.foursquare.com/v3/places/search"

def search_pois_in_bbox(bbox, limit=50):
    """
    Searches for POIs within a given bounding box using the Foursquare API.
    bbox is (min_lon, min_lat, max_lon, max_lat).
    """
    if not FSQ_API_KEY:
        logger.error("FOURSQUARE_API_KEY not set. Cannot fetch POIs.")
        return []

    # Foursquare API uses "sw" and "ne" corners for bbox.
    params = {
        "sw": f"{bbox[1]},{bbox[0]}",
        "ne": f"{bbox[3]},{bbox[2]}",
        "fields": "fsq_id,name,geocodes,categories",
        "limit": limit
    }
    headers = {
        "Accept": "application/json",
        "Authorization": FSQ_API_KEY
    }

    try:
        response = requests.get(FSQ_PLACES_ENDPOINT, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Foursquare API returned {len(data.get('results', []))} POIs.")
        return data.get('results', [])
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Foursquare POIs: {e}")
        return []