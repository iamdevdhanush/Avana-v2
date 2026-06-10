import math

import pytest

from app.utils.geo import (
    haversine_distance,
    is_within_karnataka,
    calculate_bearing,
    get_midpoint,
    generate_grid_points,
    get_district_from_coords,
)


@pytest.mark.geo
def test_haversine_distance():
    distance = haversine_distance(12.9716, 77.5946, 12.9344, 77.6101)
    assert distance > 0
    assert distance < 10
    assert isinstance(distance, float)


@pytest.mark.geo
def test_haversine_same_point():
    distance = haversine_distance(12.9716, 77.5946, 12.9716, 77.5946)
    assert distance == 0.0


@pytest.mark.geo
def test_haversine_bengaluru_to_mysore():
    distance = haversine_distance(12.9716, 77.5946, 12.2958, 76.6394)
    assert 125 < distance < 135


@pytest.mark.geo
def test_is_within_karnataka():
    assert is_within_karnataka(12.9716, 77.5946) is True


@pytest.mark.geo
def test_is_within_karnataka_outside():
    assert is_within_karnataka(28.6139, 77.2090) is False


@pytest.mark.geo
def test_is_within_karnataka_boundary():
    assert is_within_karnataka(11.5, 74.0) is True
    assert is_within_karnataka(18.0, 78.5) is True


@pytest.mark.geo
def test_is_within_karnataka_outside_boundary():
    assert is_within_karnataka(11.4, 74.0) is False
    assert is_within_karnataka(18.1, 78.5) is False
    assert is_within_karnataka(12.0, 73.9) is False
    assert is_within_karnataka(12.0, 78.6) is False


@pytest.mark.geo
def test_calculate_bearing():
    bearing = calculate_bearing(12.9716, 77.5946, 12.9344, 77.6101)
    assert 0 <= bearing <= 360
    assert isinstance(bearing, float)


@pytest.mark.geo
def test_calculate_bearing_north():
    bearing = calculate_bearing(12.0, 77.0, 13.0, 77.0)
    assert bearing == 0.0 or abs(bearing - 0.0) < 1.0


@pytest.mark.geo
def test_calculate_bearing_same_point():
    bearing = calculate_bearing(12.9716, 77.5946, 12.9716, 77.5946)
    assert 0 <= bearing <= 360


@pytest.mark.geo
def test_get_midpoint():
    mid_lat, mid_lng = get_midpoint(12.9716, 77.5946, 12.9344, 77.6101)
    assert isinstance(mid_lat, float)
    assert isinstance(mid_lng, float)
    assert abs(mid_lat - 12.953) < 0.02
    assert abs(mid_lng - 77.602) < 0.02


@pytest.mark.geo
def test_get_midpoint_same_point():
    mid_lat, mid_lng = get_midpoint(12.9716, 77.5946, 12.9716, 77.5946)
    assert abs(mid_lat - 12.9716) < 0.001
    assert abs(mid_lng - 77.5946) < 0.001


@pytest.mark.geo
def test_generate_grid_points():
    points = generate_grid_points(12.9, 77.5, 13.1, 77.7, step_km=5.0)
    assert isinstance(points, list)
    assert len(points) > 0
    for lat, lng in points:
        assert 12.9 <= lat <= 13.1
        assert 77.5 <= lng <= 77.7


@pytest.mark.geo
def test_generate_grid_points_single_point():
    points = generate_grid_points(12.97, 77.59, 12.98, 77.60, step_km=100.0)
    assert len(points) >= 1


@pytest.mark.geo
def test_get_district_from_coords():
    district = get_district_from_coords(12.9716, 77.5946)
    assert district == "Bengaluru Urban"


@pytest.mark.geo
def test_get_district_from_coords_mysuru():
    district = get_district_from_coords(12.2958, 76.6394)
    assert district == "Mysuru"


@pytest.mark.geo
def test_get_district_from_coords_not_found():
    district = get_district_from_coords(28.6139, 77.2090)
    assert district is None


@pytest.mark.geo
def test_get_district_from_coords_boundary():
    district = get_district_from_coords(12.8, 77.4)
    assert district is not None
