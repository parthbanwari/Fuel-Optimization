"""
OSRM routing client
--------------------
Uses the public OSRM demo server (router.project-osrm.org).

Why OSRM instead of ORS for routing:
  • Completely free — no API key, no rate limit, no daily quota
  • Single HTTP call returns the full route geometry
  • Simpler response format, no auth overhead
  • Faster server response time (~200-400 ms vs ~500-1000 ms for ORS)

ORS is still used for geocoding (origin/destination → coordinates) since
OSRM does not provide a geocoding endpoint.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

METERS_PER_MILE = 1_609.344


@dataclass(frozen=True)
class RouteData:
    """Parsed result of a single OSRM routing call."""

    total_distance_miles: float
    total_duration_seconds: float
    # GeoJSON LineString geometry — forwarded to API response as-is
    geometry: dict
    # List of (latitude, longitude) tuples — used by the spatial engine
    points: list[tuple[float, float]]


class RoutingError(Exception):
    """Raised when OSRM returns an error or is unreachable."""


def get_route(origin: tuple[float, float], destination: tuple[float, float]) -> RouteData:
    """
    Fetch a driving route from OSRM.

    Args:
        origin: (latitude, longitude)
        destination: (latitude, longitude)

    Returns:
        RouteData with geometry and distance.

    Raises:
        RoutingError on any failure.
    """
    base_url = settings.OSRM_BASE_URL.rstrip("/")
    # OSRM coordinate order: longitude,latitude
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    params = urlencode({
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": "false",
    })
    url = f"{base_url}/route/v1/driving/{coords}?{params}"
    request = Request(url, headers={"User-Agent": "fuel-route-optimizer/1.0"})

    try:
        with urlopen(request, timeout=settings.ORS_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RoutingError(f"OSRM request failed: {exc}") from exc
    except (json.JSONDecodeError, Exception) as exc:
        raise RoutingError(f"OSRM returned an unexpected response: {exc}") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError(
            "No drivable route found between the two locations. "
            "Make sure both locations are within the USA and accessible by road."
        )

    route_payload = payload["routes"][0]
    coordinates: list[list[float]] = route_payload["geometry"]["coordinates"]

    if len(coordinates) < 2:
        raise RoutingError("OSRM returned an empty route geometry.")

    # OSRM returns [lng, lat] — convert to (lat, lng) tuples for our spatial engine
    points = [(float(lat), float(lng)) for lng, lat in coordinates]

    # Rebuild geometry in [lng, lat] format for GeoJSON passthrough
    geometry = {
        "type": "LineString",
        "coordinates": coordinates,
    }

    logger.info(
        "OSRM route: %.1f miles, %.0f seconds, %d waypoints",
        route_payload["distance"] / METERS_PER_MILE,
        route_payload["duration"],
        len(coordinates),
    )

    return RouteData(
        total_distance_miles=route_payload["distance"] / METERS_PER_MILE,
        total_duration_seconds=route_payload["duration"],
        geometry=geometry,
        points=points,
    )
