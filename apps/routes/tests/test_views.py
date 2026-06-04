"""Integration tests for the /api/v1/routes/ endpoint."""

from unittest.mock import patch

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.fixture()
def client():
    return APIClient()


ROUTE_URL = "/api/v1/routes/"

_MOCK_RESULT = {
    "origin": {"input": "New York, NY", "latitude": 40.71, "longitude": -74.00},
    "destination": {"input": "Los Angeles, CA", "latitude": 34.05, "longitude": -118.24},
    "route": {
        "total_distance_miles": 2789.5,
        "total_duration_hours": 40.2,
        "geometry": {"type": "LineString", "coordinates": [[-74.0, 40.7], [-118.2, 34.0]]},
    },
    "fuel_stops": [
        {
            "stop_number": 1,
            "station_id": 44,
            "name": "CIRCLE K",
            "address": "I-35",
            "city": "Jarrell",
            "state": "TX",
            "latitude": 30.8,
            "longitude": -97.6,
            "distance_from_route_miles": 0.5,
            "route_distance_miles": 1400.0,
            "price_per_gallon": 2.919,
            "gallons_purchased": 25.0,
            "cost_at_stop": 72.98,
        }
    ],
    "summary": {
        "total_fuel_cost_usd": 72.98,
        "total_gallons_purchased": 25.0,
        "num_stops": 1,
        "avg_price_per_gallon": 2.919,
    },
    "meta": {
        "cached": False,
        "response_time_ms": 120,
        "stations_evaluated": 42,
        "corridor_miles": 30,
        "vehicle_range_miles": 500,
        "vehicle_mpg": 10,
    },
}


@pytest.mark.django_db
class TestRouteView:
    def test_valid_request_returns_200(self, client):
        with patch("apps.routes.views.plan_route", return_value=_MOCK_RESULT):
            resp = client.post(
                ROUTE_URL,
                {"origin": "New York, NY", "destination": "Los Angeles, CA"},
                format="json",
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "fuel_stops" in data
        assert "summary" in data
        assert "route" in data

    def test_missing_origin_returns_400(self, client):
        resp = client.post(ROUTE_URL, {"destination": "Los Angeles, CA"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_same_origin_destination_returns_400(self, client):
        resp = client.post(
            ROUTE_URL,
            {"origin": "New York, NY", "destination": "New York, NY"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_geocoding_error_returns_400(self, client):
        from apps.routes.services.route_service import RouteServiceError

        with patch(
            "apps.routes.views.plan_route",
            side_effect=RouteServiceError("Could not geocode 'XYZ'", status=400),
        ):
            resp = client.post(
                ROUTE_URL,
                {"origin": "XYZ", "destination": "Los Angeles, CA"},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in resp.json()

    def test_ors_unavailable_returns_503(self, client):
        from apps.routes.services.route_service import RouteServiceError

        with patch(
            "apps.routes.views.plan_route",
            side_effect=RouteServiceError("ORS timeout", status=503),
        ):
            resp = client.post(
                ROUTE_URL,
                {"origin": "New York, NY", "destination": "Los Angeles, CA"},
                format="json",
            )
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
