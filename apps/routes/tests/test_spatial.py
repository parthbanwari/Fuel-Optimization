"""Tests for spatial utilities — no DB or network required."""

import pytest

from apps.routes.services.spatial import (
    build_route_index,
    haversine_miles,
    simplify_route_points,
    _station_route_position_fast as station_route_position,
)

# Points are (latitude, longitude) tuples throughout.


class TestHaversine:
    def test_same_point_is_zero(self):
        assert haversine_miles(40.0, -74.0, 40.0, -74.0) == pytest.approx(0.0)

    def test_known_distance(self):
        # NYC to LA: roughly 2,445 miles great-circle
        dist = haversine_miles(40.7128, -74.0059, 34.0522, -118.2437)
        assert 2_400 < dist < 2_500


class TestSimplifyRoutePoints:
    def test_preserves_endpoints(self):
        pts = [(float(i), 0.0) for i in range(100)]  # 100 points spaced ~69 miles apart
        result = simplify_route_points(pts, min_spacing_miles=100.0)
        assert result[0] == pts[0]
        assert result[-1] == pts[-1]

    def test_reduces_dense_polyline(self):
        # Dense: 1000 points ~0.1° apart (≈ 7 miles each)
        pts = [(i * 0.1, 0.0) for i in range(1000)]
        simplified = simplify_route_points(pts, min_spacing_miles=50.0)
        assert len(simplified) < len(pts)
        assert simplified[0] == pts[0]
        assert simplified[-1] == pts[-1]

    def test_short_route_unchanged(self):
        pts = [(0.0, 0.0), (1.0, 0.0)]
        assert simplify_route_points(pts) == pts


class TestBuildRouteIndex:
    def test_single_segment(self):
        # 1° latitude ≈ 69 miles
        pts = [(0.0, 0.0), (1.0, 0.0)]  # (lat, lng)
        idx = build_route_index(pts)
        assert idx["cumulative"][0] == 0.0
        assert 65 < idx["cumulative"][1] < 75
        assert idx["total_miles"] == idx["cumulative"][-1]

    def test_cumulative_order(self):
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        idx = build_route_index(pts)
        assert idx["cumulative"][0] < idx["cumulative"][1] < idx["cumulative"][2]


class TestStationRoutePosition:
    def test_station_on_route(self):
        # Route goes due north; station exactly on the midpoint
        pts = [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
        idx = build_route_index(pts)
        marker, dist = station_route_position(1.0, 0.0, idx)
        assert dist == pytest.approx(0.0, abs=0.5)
        assert marker == pytest.approx(idx["cumulative"][1], abs=2.0)

    def test_station_off_route(self):
        pts = [(0.0, 0.0), (2.0, 0.0)]
        idx = build_route_index(pts)
        # Station 1° east of midpoint — roughly 50-80 miles at equator
        marker, dist = station_route_position(1.0, 1.0, idx)
        assert 40 < dist < 90
