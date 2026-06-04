from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_Station = dict


def optimize_fuel_stops(
    stations_on_route: list[_Station],
    total_distance_miles: float,
    max_range_miles: float = 500.0,
    mpg: float = 10.0,
) -> tuple[list[dict], float]:
    if total_distance_miles <= max_range_miles and not stations_on_route:
        return [], 0.0

    stations = sorted(stations_on_route, key=lambda s: s["route_distance"])
    n = len(stations)
    current_pos: float = 0.0
    current_fuel: float = max_range_miles
    stops: list[dict] = []
    total_cost: float = 0.0
    ptr: int = 0

    while current_pos + current_fuel < total_distance_miles:
        while ptr < n and stations[ptr]["route_distance"] <= current_pos:
            ptr += 1

        if ptr >= n:
            raise ValueError(
                f"No fuel stations available beyond mile {current_pos:.1f}. "
                "Ensure stations are geocoded (run: load_coordinates or geocode_stations)."
            )

        reachable = [
            j for j in range(ptr, n)
            if stations[j]["route_distance"] <= current_pos + current_fuel
        ]

        if not reachable:
            raise ValueError(
                f"No reachable station from mile {current_pos:.1f} "
                f"(tank covers to mile {current_pos + current_fuel:.1f})."
            )

        best_j = min(reachable, key=lambda j: stations[j]["price"])
        station = stations[best_j]
        dist_to_station = station["route_distance"] - current_pos
        fuel_on_arrival = current_fuel - dist_to_station

        stations_ahead = [stations[j] for j in range(best_j + 1, n)]
        dest_in_range = (station["route_distance"] + max_range_miles) >= total_distance_miles

        if not stations_ahead:
            fuel_to_dest = total_distance_miles - station["route_distance"]
            gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)
        else:
            in_range_from_here = [
                s for s in stations_ahead
                if s["route_distance"] <= station["route_distance"] + max_range_miles
            ]
            if not in_range_from_here:
                if dest_in_range:
                    fuel_to_dest = total_distance_miles - station["route_distance"]
                    gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)
                else:
                    gallons = (max_range_miles - fuel_on_arrival) / mpg
            else:
                cheapest_ahead = min(in_range_from_here, key=lambda s: s["price"])
                if cheapest_ahead["price"] < station["price"]:
                    reach = cheapest_ahead["route_distance"] - station["route_distance"]
                    gallons = max(0.0, (reach - fuel_on_arrival) / mpg)
                else:
                    if dest_in_range:
                        fuel_to_dest = total_distance_miles - station["route_distance"]
                        gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)
                    else:
                        gallons = (max_range_miles - fuel_on_arrival) / mpg

        gallons = min(gallons, (max_range_miles - fuel_on_arrival) / mpg)
        gallons = max(0.0, gallons)
        cost = gallons * station["price"]
        total_cost += cost
        current_pos = station["route_distance"]
        current_fuel = fuel_on_arrival + gallons * mpg
        ptr = best_j + 1

        if gallons > 0.001:
            stops.append({
                "stop_number": len(stops) + 1,
                "station_id": station["station_id"],
                "name": station["name"],
                "address": station.get("address", ""),
                "city": station["city"],
                "state": station["state"],
                "latitude": station["latitude"],
                "longitude": station["longitude"],
                "distance_from_route_miles": round(station.get("distance_from_route", 0), 2),
                "route_distance_miles": round(station["route_distance"], 1),
                "price_per_gallon": round(station["price"], 5),
                "gallons_purchased": round(gallons, 3),
                "cost_at_stop": round(cost, 2),
            })

    return stops, round(total_cost, 2)
