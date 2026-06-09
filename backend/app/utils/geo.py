import math
import logging
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

KARNATAKA_BOUNDS = {
    "min_lat": 11.5,
    "max_lat": 18.0,
    "min_lng": 74.0,
    "max_lng": 78.5,
}

DISTRICT_BOUNDS: dict = {
    "Bengaluru Urban": (12.8, 13.2, 77.4, 77.8),
    "Bengaluru Rural": (13.0, 13.4, 77.2, 77.7),
    "Mysuru": (12.1, 12.5, 76.5, 76.8),
    "Dakshina Kannada": (12.7, 13.2, 74.8, 75.2),
    "Udupi": (13.2, 13.6, 74.6, 74.9),
    "Belagavi": (15.5, 16.2, 74.2, 75.1),
    "Dharwad": (15.3, 15.6, 74.8, 75.2),
    "Hubballi": (15.3, 15.4, 74.9, 75.1),
    "Mangaluru": (12.8, 13.0, 74.8, 74.9),
    "Shivamogga": (13.8, 14.2, 75.0, 75.6),
    "Tumakuru": (13.2, 13.8, 76.8, 77.4),
    "Hassan": (12.8, 13.3, 75.8, 76.4),
    "Mandya": (12.4, 12.8, 76.5, 77.2),
    "Chikkamagaluru": (13.0, 13.6, 75.4, 76.0),
    "Kolar": (12.9, 13.3, 77.9, 78.4),
    "Ballari": (15.0, 15.6, 76.6, 77.0),
    "Vijayapura": (16.6, 17.0, 75.4, 75.9),
    "Kalaburagi": (17.0, 17.6, 76.6, 77.2),
    "Raichur": (16.0, 16.5, 76.8, 77.4),
    "Koppal": (15.2, 15.6, 75.8, 76.4),
    "Gadag": (15.2, 15.6, 75.4, 75.8),
    "Haveri": (14.6, 15.0, 75.2, 75.8),
    "Davangere": (14.2, 14.6, 75.6, 76.2),
    "Chitradurga": (14.0, 14.6, 76.0, 76.8),
    "Ramanagara": (12.6, 12.9, 77.1, 77.4),
    "Kodagu": (12.2, 12.6, 75.6, 76.0),
    "Chamarajanagara": (11.8, 12.2, 76.6, 77.2),
    "Bagalkote": (16.0, 16.4, 75.4, 75.8),
    "Bidar": (17.8, 18.2, 77.2, 77.6),
    "Yadgir": (16.6, 17.0, 76.8, 77.4),
    "Uttara Kannada": (14.4, 15.0, 74.4, 74.8),
}


def haversine_distance(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 4)


def is_within_karnataka(lat: float, lng: float) -> bool:
    return (
        KARNATAKA_BOUNDS["min_lat"] <= lat <= KARNATAKA_BOUNDS["max_lat"]
        and KARNATAKA_BOUNDS["min_lng"] <= lng <= KARNATAKA_BOUNDS["max_lng"]
    )


def calculate_bearing(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    y = math.sin(dlng) * math.cos(math.radians(lat2))
    x = (
        math.cos(math.radians(lat1)) * math.sin(math.radians(lat2))
        - math.sin(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.cos(dlng)
    )
    bearing = math.degrees(math.atan2(y, x))
    return (bearing + 360) % 360


def get_midpoint(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> Tuple[float, float]:
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    bx = math.cos(lat2_rad) * math.cos(dlng)
    by = math.cos(lat2_rad) * math.sin(dlng)
    lat_mid = math.atan2(
        math.sin(lat1_rad) + math.sin(lat2_rad),
        math.sqrt((math.cos(lat1_rad) + bx) ** 2 + by ** 2),
    )
    lng_mid = math.radians(lng1) + math.atan2(by, math.cos(lat1_rad) + bx)
    return (round(math.degrees(lat_mid), 6), round(math.degrees(lng_mid), 6))


def generate_grid_points(
    sw_lat: float,
    sw_lng: float,
    ne_lat: float,
    ne_lng: float,
    step_km: float = 2.0,
) -> List[Tuple[float, float]]:
    lat_step = step_km / 111.0
    lng_step = step_km / (111.0 * math.cos(math.radians((sw_lat + ne_lat) / 2)))
    points = []
    lat = sw_lat
    while lat <= ne_lat:
        lng = sw_lng
        while lng <= ne_lng:
            points.append((round(lat, 6), round(lng, 6)))
            lng += lng_step
        lat += lat_step
    return points


def get_district_from_coords(lat: float, lng: float) -> Optional[str]:
    for district, (min_lat, max_lat, min_lng, max_lng) in DISTRICT_BOUNDS.items():
        if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
            return district
    return None
