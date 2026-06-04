from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from apps.stations.models import FuelStation

EARTH_RADIUS_MILES = 3_958.8


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1, lat2, dlat, dlng = (
        math.radians(lat1), math.radians(lat2),
        math.radians(lat2 - lat1), math.radians(lng2 - lng1),
    )
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def simplify_route_points(
    points: list[tuple[float, float]],
    min_spacing_miles: float = 5.0,
) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return list(points)

    simplified = [points[0]]
    accumulated = 0.0
    prev = points[0]

    for pt in points[1:-1]:
        accumulated += haversine_miles(prev[0], prev[1], pt[0], pt[1])
        prev = pt
        if accumulated >= min_spacing_miles:
            simplified.append(pt)
            accumulated = 0.0

    if simplified[-1] != points[-1]:
        simplified.append(points[-1])

    return simplified


def build_route_index(points: list[tuple[float, float]]) -> dict:
    cumulative: list[float] = [0.0]
    for i in range(1, len(points)):
        lat1, lng1 = points[i - 1]
        lat2, lng2 = points[i]
        cumulative.append(cumulative[-1] + haversine_miles(lat1, lng1, lat2, lng2))
    return {"points": points, "cumulative": cumulative, "total_miles": cumulative[-1]}


def _station_route_position_fast(
    station_lat: float,
    station_lng: float,
    route_index: dict,
) -> tuple[float, float]:
    points = route_index["points"]
    cumulative = route_index["cumulative"]

    # One cosine per station; remaining segment checks are pure arithmetic
    cos_lat = math.cos(math.radians(station_lat))

    def to_xy(lat: float, lng: float) -> tuple[float, float]:
        return (math.radians(lng) * cos_lat * EARTH_RADIUS_MILES,
                math.radians(lat) * EARTH_RADIUS_MILES)

    sx, sy = to_xy(station_lat, station_lng)
    best_dist = math.inf
    best_marker = 0.0

    for i in range(len(points) - 1):
        ax, ay = to_xy(points[i][0], points[i][1])
        bx, by = to_xy(points[i + 1][0], points[i + 1][1])
        dx, dy = bx - ax, by - ay
        seg_sq = dx * dx + dy * dy
        t = 0.0 if seg_sq == 0.0 else max(0.0, min(1.0, ((sx - ax) * dx + (sy - ay) * dy) / seg_sq))
        dist = math.hypot(sx - (ax + t * dx), sy - (ay + t * dy))
        if dist < best_dist:
            best_dist = dist
            best_marker = cumulative[i] + t * (cumulative[i + 1] - cumulative[i])

    return best_marker, best_dist


def find_stations_near_route(
    stations_qs: "QuerySet[FuelStation]",
    route_index: dict,
    corridor_miles: float = 30.0,
) -> list[dict]:
    points = route_index["points"]
    lats = [p[0] for p in points]
    lngs = [p[1] for p in points]
    avg_lat = sum(lats) / len(lats)
    lat_buf = corridor_miles / 69.0
    lng_buf = corridor_miles / max(1.0, 69.0 * math.cos(math.radians(avg_lat)))

    nearby_qs = (
        stations_qs
        .filter(
            latitude__isnull=False,
            longitude__isnull=False,
            latitude__gte=min(lats) - lat_buf,
            latitude__lte=max(lats) + lat_buf,
            longitude__gte=min(lngs) - lng_buf,
            longitude__lte=max(lngs) + lng_buf,
        )
        .only("opis_id", "name", "address", "city", "state", "latitude", "longitude", "retail_price")
    )

    results: list[dict] = []
    for station in nearby_qs.iterator(chunk_size=500):
        mile_marker, dist = _station_route_position_fast(station.latitude, station.longitude, route_index)
        if dist <= corridor_miles:
            results.append({
                "station_id": station.opis_id,
                "name": station.name,
                "address": station.address,
                "city": station.city,
                "state": station.state,
                "latitude": station.latitude,
                "longitude": station.longitude,
                "price": float(station.retail_price),
                "route_distance": mile_marker,
                "distance_from_route": dist,
            })

    return sorted(results, key=lambda s: (s["route_distance"], s["price"]))
