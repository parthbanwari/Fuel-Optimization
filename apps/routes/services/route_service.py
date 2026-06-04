from __future__ import annotations

import hashlib
import logging
import time

from django.conf import settings
from django.core.cache import cache

from apps.stations.models import FuelStation

from .fuel_optimizer import optimize_fuel_stops
from .geocoder import GeocodingError, geocode_address
from .routing_client import RoutingError, RouteData, get_route
from .spatial import build_route_index, find_stations_near_route, simplify_route_points

logger = logging.getLogger(__name__)


class RouteServiceError(Exception):

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def plan_route(origin_input: str, destination_input: str) -> dict:

    t_start = time.monotonic()

    try:
        origin_coords = geocode_address(origin_input)
        dest_coords = geocode_address(destination_input)
    except GeocodingError as exc:
        raise RouteServiceError(str(exc), status=400) from exc

    cache_key = _route_cache_key(origin_coords, dest_coords)
    route_data: RouteData | None = cache.get(cache_key)
    was_cached = route_data is not None

    if route_data is None:
        try:
            route_data = get_route(origin_coords, dest_coords)
        except RoutingError as exc:
            raise RouteServiceError(str(exc), status=503) from exc
        cache.set(cache_key, route_data, timeout=settings.ROUTE_CACHE_TTL)
        logger.info(
            "OSRM route fetched: %.1f miles, %d raw waypoints (%s → %s)",
            route_data.total_distance_miles,
            len(route_data.points),
            origin_input,
            destination_input,
        )
    else:
        logger.debug("Route served from cache: %s → %s", origin_input, destination_input)

    spacing = settings.ROUTE_SIMPLIFY_SPACING_MILES
    simplified = simplify_route_points(route_data.points, min_spacing_miles=spacing)
    logger.debug(
        "Route simplified: %d → %d points (%.1f-mile spacing)",
        len(route_data.points), len(simplified), spacing,
    )

    route_index = build_route_index(simplified)

    corridor = settings.ROUTE_CORRIDOR_MILES
    stations_on_route = find_stations_near_route(
        FuelStation.objects.all(), route_index, corridor_miles=corridor
    )
    logger.debug("%d stations found within %d-mile corridor", len(stations_on_route), corridor)

    try:
        stops, total_cost = optimize_fuel_stops(
            stations_on_route,
            total_distance_miles=route_data.total_distance_miles,
            max_range_miles=settings.VEHICLE_MAX_RANGE_MILES,
            mpg=settings.VEHICLE_MPG,
        )
    except ValueError as exc:
        raise RouteServiceError(str(exc), status=400) from exc

    total_gallons = sum(s["gallons_purchased"] for s in stops)
    avg_price = (total_cost / total_gallons) if total_gallons > 0 else 0.0

    response_ms = int((time.monotonic() - t_start) * 1000)
    logger.info(
        "Route planned in %d ms — %d stops, $%.2f fuel (%s → %s)",
        response_ms, len(stops), total_cost, origin_input, destination_input,
    )

    return {
        "origin": {
            "input": origin_input,
            "latitude": origin_coords[0],
            "longitude": origin_coords[1],
        },
        "destination": {
            "input": destination_input,
            "latitude": dest_coords[0],
            "longitude": dest_coords[1],
        },
        "route": {
            "total_distance_miles": round(route_data.total_distance_miles, 2),
            "total_duration_hours": round(route_data.total_duration_seconds / 3600, 2),
            "total_duration_human": _format_duration(route_data.total_duration_seconds),
            "geometry": route_data.geometry,
        },
        "fuel_stops": stops,
        "summary": {
            "total_fuel_cost_usd": total_cost,
            "total_gallons_purchased": round(total_gallons, 3),
            "num_stops": len(stops),
            "avg_price_per_gallon": round(avg_price, 4),
        },
        "meta": {
            "cached": was_cached,
            "response_time_ms": response_ms,
            "stations_evaluated": len(stations_on_route),
            "corridor_miles": corridor,
            "vehicle_range_miles": settings.VEHICLE_MAX_RANGE_MILES,
            "vehicle_mpg": settings.VEHICLE_MPG,
            "route_waypoints_raw": len(route_data.points),
            "route_waypoints_simplified": len(simplified),
        },
    }


def _route_cache_key(origin: tuple[float, float], dest: tuple[float, float]) -> str:
    raw = f"{origin[0]:.4f},{origin[1]:.4f}:{dest[0]:.4f},{dest[1]:.4f}"
    return "route:" + hashlib.sha256(raw.encode()).hexdigest()[:24]


def _format_duration(total_seconds: float) -> str:
    """Convert seconds to a human-readable string like '19h 46m'."""
    total_minutes = int(total_seconds // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if hours == 0:
        return f"{minutes}m"
    if minutes == 0:
        return f"{hours}h"
    return f"{hours}h {minutes}m"
