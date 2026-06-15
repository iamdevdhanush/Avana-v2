"""
Karnataka district/city geographic data and coordinate resolution.
Used when source datasets lack latitude/longitude.
"""
from typing import Optional, Tuple


DISTRICT_CENTROIDS = {
    "Bengaluru Urban": (12.9716, 77.5946),
    "Bengaluru Rural": (13.1000, 77.4000),
    "Mysuru": (12.2958, 76.6394),
    "Mysore": (12.2958, 76.6394),
    "Dakshina Kannada": (12.8700, 74.8800),
    "Udupi": (13.3409, 74.7421),
    "Belagavi": (15.8497, 74.4977),
    "Belgaum": (15.8497, 74.4977),
    "Dharwad": (15.4589, 75.0078),
    "Hubballi": (15.3647, 75.1240),
    "Hubli": (15.3647, 75.1240),
    "Mangaluru": (12.9141, 74.8560),
    "Mangalore": (12.9141, 74.8560),
    "Shivamogga": (13.9299, 75.5681),
    "Shimoga": (13.9299, 75.5681),
    "Tumakuru": (13.3379, 77.1173),
    "Tumkur": (13.3379, 77.1173),
    "Hassan": (13.0055, 76.0913),
    "Mandya": (12.5243, 76.8958),
    "Chikkamagaluru": (13.3161, 75.7720),
    "Chikmagalur": (13.3161, 75.7720),
    "Kolar": (13.1357, 78.1295),
    "Ballari": (15.1394, 76.9214),
    "Bellary": (15.1394, 76.9214),
    "Vijayapura": (16.8302, 75.7100),
    "Bijapur": (16.8302, 75.7100),
    "Kalaburagi": (17.3297, 76.8343),
    "Gulbarga": (17.3297, 76.8343),
    "Raichur": (16.2059, 77.3567),
    "Koppal": (15.3500, 76.1500),
    "Gadag": (15.4167, 75.6167),
    "Haveri": (14.8000, 75.4000),
    "Davangere": (14.4667, 75.9833),
    "Chitradurga": (14.2333, 76.4000),
    "Ramanagara": (12.7200, 77.2800),
    "Kodagu": (12.4200, 75.7300),
    "Coorg": (12.4200, 75.7300),
    "Chamarajanagara": (11.9236, 76.9397),
    "Chamarajanagar": (11.9236, 76.9397),
    "Bagalkote": (16.1833, 75.7000),
    "Bagalkot": (16.1833, 75.7000),
    "Bidar": (17.9133, 77.5300),
    "Yadgir": (16.7667, 77.1333),
    "Yadgiri": (16.7667, 77.1333),
    "Uttara Kannada": (14.8500, 74.5500),
    "North Canara": (14.8500, 74.5500),
    "Karwar": (14.8130, 74.1297),
    "Bengaluru": (12.9716, 77.5946),
    "Bangalore": (12.9716, 77.5946),
}

CITY_CENTROIDS = {
    "Bengaluru": (12.9716, 77.5946),
    "Bangalore": (12.9716, 77.5946),
    "Mysuru": (12.2958, 76.6394),
    "Mysore": (12.2958, 76.6394),
    "Mangaluru": (12.9141, 74.8560),
    "Mangalore": (12.9141, 74.8560),
    "Hubballi": (15.3647, 75.1240),
    "Hubli": (15.3647, 75.1240),
    "Dharwad": (15.4589, 75.0078),
    "Belagavi": (15.8497, 74.4977),
    "Belgaum": (15.8497, 74.4977),
    "Kalaburagi": (17.3297, 76.8343),
    "Gulbarga": (17.3297, 76.8343),
    "Shivamogga": (13.9299, 75.5681),
    "Shimoga": (13.9299, 75.5681),
    "Ballari": (15.1394, 76.9214),
    "Bellary": (15.1394, 76.9214),
    "Tumakuru": (13.3379, 77.1173),
    "Tumkur": (13.3379, 77.1173),
    "Udupi": (13.3409, 74.7421),
    "Hassan": (13.0055, 76.0913),
    "Davangere": (14.4667, 75.9833),
    "Raichur": (16.2059, 77.3567),
    "Bidar": (17.9133, 77.5300),
    "Chitradurga": (14.2333, 76.4000),
    "Kolar": (13.1357, 78.1295),
    "Mandya": (12.5243, 76.8958),
    "Chikkamagaluru": (13.3161, 75.7720),
    "Chikmagalur": (13.3161, 75.7720),
    "Vijayapura": (16.8302, 75.7100),
    "Bijapur": (16.8302, 75.7100),
    "Ramanagara": (12.7200, 77.2800),
    "Kodagu": (13.1000, 75.6000),
    "Coorg": (13.1000, 75.6000),
    "Chamarajanagara": (11.9236, 76.9397),
    "Chamarajanagar": (11.9236, 76.9397),
    "Yadgir": (16.7667, 77.1333),
    "Gadag": (15.4167, 75.6167),
    "Haveri": (14.8000, 75.4000),
    "Koppal": (15.3500, 76.1500),
    "Bagalkote": (16.1833, 75.7000),
    "Bagalkot": (16.1833, 75.7000),
}

# City → district mapping for cities that are within districts
CITY_TO_DISTRICT = {
    "Bengaluru": "Bengaluru Urban",
    "Bangalore": "Bengaluru Urban",
    "Mysuru": "Mysuru",
    "Mysore": "Mysuru",
    "Mangaluru": "Dakshina Kannada",
    "Mangalore": "Dakshina Kannada",
    "Hubballi": "Dharwad",
    "Hubli": "Dharwad",
    "Belagavi": "Belagavi",
    "Belgaum": "Belagavi",
    "Kalaburagi": "Kalaburagi",
    "Gulbarga": "Kalaburagi",
    "Shivamogga": "Shivamogga",
    "Shimoga": "Shivamogga",
    "Ballari": "Ballari",
    "Bellary": "Ballari",
    "Tumakuru": "Tumakuru",
    "Tumkur": "Tumakuru",
    "Udupi": "Udupi",
    "Hassan": "Hassan",
    "Davangere": "Davangere",
    "Raichur": "Raichur",
    "Bidar": "Bidar",
    "Chitradurga": "Chitradurga",
    "Kolar": "Kolar",
    "Mandya": "Mandya",
    "Chikkamagaluru": "Chikkamagaluru",
    "Chikmagalur": "Chikkamagaluru",
    "Vijayapura": "Vijayapura",
    "Bijapur": "Vijayapura",
    "Ramanagara": "Ramanagara",
    "Chamarajanagara": "Chamarajanagara",
    "Chamarajanagar": "Chamarajanagara",
    "Yadgir": "Yadgir",
    "Gadag": "Gadag",
    "Haveri": "Haveri",
    "Koppal": "Koppal",
    "Bagalkote": "Bagalkote",
    "Bagalkot": "Bagalkote",
    "Karwar": "Uttara Kannada",
}


def resolve_coordinates(
    district: Optional[str] = None,
    city: Optional[str] = None,
) -> Tuple[Optional[float], Optional[float]]:
    if city and city.strip():
        normalized = city.strip().title()
        if normalized in CITY_CENTROIDS:
            return CITY_CENTROIDS[normalized]
    if district and district.strip():
        normalized = _normalize_district_name(district.strip())
        if normalized in DISTRICT_CENTROIDS:
            return DISTRICT_CENTROIDS[normalized]
    return (None, None)


def resolve_district(district: str) -> Optional[str]:
    return _normalize_district_name(district.strip())


def resolve_district_from_city(city: str) -> Optional[str]:
    normalized = city.strip().title()
    return CITY_TO_DISTRICT.get(normalized)


def _normalize_district_name(name: str) -> Optional[str]:
    name_lower = name.lower().strip()

    mapping = {
        "bengaluru urban": "Bengaluru Urban",
        "bengaluru rural": "Bengaluru Rural",
        "bangalore urban": "Bengaluru Urban",
        "bangalore rural": "Bengaluru Rural",
        "bengaluru": "Bengaluru Urban",
        "bangalore": "Bengaluru Urban",
        "mysuru": "Mysuru",
        "mysore": "Mysuru",
        "dakshina kannada": "Dakshina Kannada",
        "dakshin kannada": "Dakshina Kannada",
        "south canara": "Dakshina Kannada",
        "belagavi": "Belagavi",
        "belgaum": "Belagavi",
        "dharwad": "Dharwad",
        "hubballi": "Dharwad",
        "hubli dharwad": "Dharwad",
        "hubli-dharwad": "Dharwad",
        "shivamogga": "Shivamogga",
        "shimoga": "Shivamogga",
        "tumakuru": "Tumakuru",
        "tumkur": "Tumakuru",
        "chikkamagaluru": "Chikkamagaluru",
        "chikmagalur": "Chikkamagaluru",
        "chikkamagalore": "Chikkamagaluru",
        "ballari": "Ballari",
        "bellary": "Ballari",
        "vijayapura": "Vijayapura",
        "bijapur": "Vijayapura",
        "kalaburagi": "Kalaburagi",
        "gulbarga": "Kalaburagi",
        "chamarajanagara": "Chamarajanagara",
        "chamarajanagar": "Chamarajanagara",
        "chamrajnagar": "Chamarajanagara",
        "bagalkote": "Bagalkote",
        "bagalkot": "Bagalkote",
        "yadgir": "Yadgir",
        "yadgiri": "Yadgir",
        "uttara kannada": "Uttara Kannada",
        "uttar kannada": "Uttara Kannada",
        "north canara": "Uttara Kannada",
        "kodagu": "Kodagu",
        "coorg": "Kodagu",
        "ramanagara": "Ramanagara",
        "ramanagaram": "Ramanagara",
        "mangaluru": "Dakshina Kannada",
        "mangalore": "Dakshina Kannada",
        "udupi": "Udupi",
        "hassan": "Hassan",
        "mandya": "Mandya",
        "kolar": "Kolar",
        "raichur": "Raichur",
        "koppal": "Koppal",
        "gadag": "Gadag",
        "haveri": "Haveri",
        "davangere": "Davangere",
        "chitradurga": "Chitradurga",
        "bidar": "Bidar",
    }

    return mapping.get(name_lower)
