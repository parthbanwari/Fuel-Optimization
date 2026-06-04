from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_DIRECTIONS_URL = f"{settings.ORS_BASE_URL}/v2/directions/driving-car/geojson"

METERS_PER_MILE = 1_609.344


@dataclass(frozen=True)
class RouteData:
    total_distance_miles: float
    total_duration_seconds: float
    geometry: dict
    waypoints: list[list[float]]


class ORSError(Exception):
    pass


def get_route(origin: tuple[float, float], destination: tuple[float, float]) -> RouteData:
    if not settings.ORS_API_KEY:
        raise ORSError("ORS_API_KEY is not configured. Sign up at https://openrouteservice.org.")

    # ORS expects [lng, lat] order
    coordinates = [[origin[1], origin[0]], [destination[1], destination[0]]]
    headers = {
        "Authorization": settings.ORS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json, application/geo+json",
    }

    for attempt in range(1, settings.ORS_MAX_RETRIES + 1):
        try:
            response = requests.post(
                _DIRECTIONS_URL,
                json={"coordinates": coordinates},
                headers=headers,
                timeout=settings.ORS_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return _parse_response(response.json())
        except requests.exceptions.Timeout:
            logger.warning("ORS timeout (attempt %d/%d)", attempt, settings.ORS_MAX_RETRIES)
            if attempt == settings.ORS_MAX_RETRIES:
                raise ORSError("ORS API timed out after multiple retries.")
        except requests.exceptions.HTTPError as exc:
            _handle_http_error(exc)
        except requests.exceptions.RequestException as exc:
            raise ORSError(f"ORS request failed: {exc}") from exc

    raise ORSError("Unexpected end of retry loop.")  # pragma: no cover


def _parse_response(data: dict) -> RouteData:
    try:
        feature = data["features"][0]
        summary = feature["properties"]["summary"]
        geometry = feature["geometry"]
        waypoints: list[list[float]] = geometry["coordinates"]
    except (KeyError, IndexError) as exc:
        raise ORSError(f"Unexpected ORS response structure: {exc}") from exc

    return RouteData(
        total_distance_miles=summary["distance"] / METERS_PER_MILE,
        total_duration_seconds=summary["duration"],
        geometry=geometry,
        waypoints=waypoints,
    )


def _handle_http_error(exc: requests.exceptions.HTTPError) -> None:
    status = exc.response.status_code
    try:
        body = exc.response.json()
        message = body.get("error", {}).get("message") or body.get("message") or str(body)
    except Exception:
        message = exc.response.text[:200]

    if status == 401:
        raise ORSError("Invalid ORS API key.")
    if status == 403:
        raise ORSError("ORS API quota exceeded.")
    if status == 404:
        raise ORSError(f"ORS could not find a route: {message}")
    raise ORSError(f"ORS API error {status}: {message}")
