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
    total_distance_miles: float
    total_duration_seconds: float
    geometry: dict
    points: list[tuple[float, float]]


class RoutingError(Exception):
    pass


def get_route(origin: tuple[float, float], destination: tuple[float, float]) -> RouteData:
    base_url = settings.OSRM_BASE_URL.rstrip("/")
    # OSRM expects longitude,latitude order
    coords = f"{origin[1]},{origin[0]};{destination[1]},{destination[0]}"
    params = urlencode({"overview": "full", "geometries": "geojson", "steps": "false", "alternatives": "false"})
    url = f"{base_url}/route/v1/driving/{coords}?{params}"

    try:
        with urlopen(Request(url, headers={"User-Agent": "fuel-route-optimizer/1.0"}), timeout=settings.ORS_TIMEOUT_SECONDS) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as exc:
        raise RoutingError(f"OSRM request failed: {exc}") from exc
    except Exception as exc:
        raise RoutingError(f"OSRM returned an unexpected response: {exc}") from exc

    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError("No drivable route found. Make sure both locations are within the USA.")

    route_payload = payload["routes"][0]
    coordinates: list[list[float]] = route_payload["geometry"]["coordinates"]

    if len(coordinates) < 2:
        raise RoutingError("OSRM returned an empty route geometry.")

    # OSRM returns [lng, lat] — flip to (lat, lng) for internal use
    points = [(float(lat), float(lng)) for lng, lat in coordinates]

    logger.info("OSRM route: %.1f miles, %d waypoints", route_payload["distance"] / METERS_PER_MILE, len(coordinates))

    return RouteData(
        total_distance_miles=route_payload["distance"] / METERS_PER_MILE,
        total_duration_seconds=route_payload["duration"],
        geometry={"type": "LineString", "coordinates": coordinates},
        points=points,
    )
