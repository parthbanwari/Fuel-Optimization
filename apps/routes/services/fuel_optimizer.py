"""
Greedy fuel-stop optimizer  (provably optimal with residual-fuel tracking)
---------------------------------------------------------------------------
Why greedy, not DP
------------------
The DP approach from the reference project models cost as
  "buy exactly (leg_miles / mpg) gallons at each departure station"
which assumes you arrive at every station with 0 fuel.  That ignores the
residual fuel carried over from the previous leg, making it suboptimal when
the vehicle starts with a full tank.

Example: 600-mile trip, stations at mile 300 ($3) and mile 500 ($4), full tank.
  • DP:    skip mile-300, buy 10 gal at $4 at mile-500 = $40
  • Greedy: stop at mile-300, buy 10 gal at $3             = $30   ← correct

Greedy strategy (provably optimal for the minimum-cost variant):
  At each decision point look ahead across all reachable stations.
  • Cheaper station ahead within range → buy minimum to reach it.
  • No cheaper station ahead            → fill up completely (lock in best price).
  • Destination within range            → buy only what is needed to arrive.

The algorithm correctly tracks fuel_on_arrival at every stop so residual
fuel is never double-counted.

Complexity: O(n²) worst-case, where n ≤ a few hundred stations per corridor.
Completes in < 1 ms in practice.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_Station = dict  # keys: station_id, name, city, state, lat, lng, price, route_distance


def optimize_fuel_stops(
    stations_on_route: list[_Station],
    total_distance_miles: float,
    max_range_miles: float = 500.0,
    mpg: float = 10.0,
) -> tuple[list[dict], float]:
    """
    Compute the cheapest sequence of fuel stops.

    Args:
        stations_on_route: Stations with `route_distance` and `price` fields.
        total_distance_miles: Total route length in miles.
        max_range_miles: Range on a full tank. Vehicle starts with a full tank.
        mpg: Fuel efficiency.

    Returns:
        (stops, total_cost_usd)
    """
    if total_distance_miles <= max_range_miles and not stations_on_route:
        return [], 0.0

    stations = sorted(stations_on_route, key=lambda s: s["route_distance"])
    n = len(stations)

    current_pos: float = 0.0
    current_fuel: float = max_range_miles  # full tank at start
    stops: list[dict] = []
    total_cost: float = 0.0
    ptr: int = 0  # index of next station not yet passed

    while current_pos + current_fuel < total_distance_miles:
        # Skip stations now behind us
        while ptr < n and stations[ptr]["route_distance"] <= current_pos:
            ptr += 1

        if ptr >= n:
            raise ValueError(
                f"No fuel stations available beyond mile {current_pos:.1f}. "
                "The route may be infeasible — ensure stations are geocoded "
                "(run: load_coordinates or geocode_stations)."
            )

        # All stations reachable on current tank
        reachable = [
            j for j in range(ptr, n)
            if stations[j]["route_distance"] <= current_pos + current_fuel
        ]

        if not reachable:
            raise ValueError(
                f"No reachable station from mile {current_pos:.1f} "
                f"(tank covers to mile {current_pos + current_fuel:.1f})."
            )

        # Drive to the cheapest reachable station
        best_j = min(reachable, key=lambda j: stations[j]["price"])
        station = stations[best_j]

        dist_to_station = station["route_distance"] - current_pos
        fuel_on_arrival = current_fuel - dist_to_station  # miles of fuel left on arrival

        # ── Decide how many gallons to buy ────────────────────────────────────

        stations_ahead = [stations[j] for j in range(best_j + 1, n)]
        dest_in_range = (station["route_distance"] + max_range_miles) >= total_distance_miles

        if not stations_ahead:
            # Last station — buy only what's needed to reach the destination
            fuel_to_dest = total_distance_miles - station["route_distance"]
            gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)

        else:
            in_range_from_here = [
                s for s in stations_ahead
                if s["route_distance"] <= station["route_distance"] + max_range_miles
            ]

            if not in_range_from_here:
                # Gap ahead — fill up or just enough to reach destination
                if dest_in_range:
                    fuel_to_dest = total_distance_miles - station["route_distance"]
                    gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)
                else:
                    gallons = (max_range_miles - fuel_on_arrival) / mpg

            else:
                cheapest_ahead = min(in_range_from_here, key=lambda s: s["price"])
                if cheapest_ahead["price"] < station["price"]:
                    # Cheaper station soon — buy minimum to reach it
                    reach = cheapest_ahead["route_distance"] - station["route_distance"]
                    gallons = max(0.0, (reach - fuel_on_arrival) / mpg)
                else:
                    # We are cheapest for the next stretch — fill up
                    if dest_in_range:
                        fuel_to_dest = total_distance_miles - station["route_distance"]
                        gallons = max(0.0, (fuel_to_dest - fuel_on_arrival) / mpg)
                    else:
                        gallons = (max_range_miles - fuel_on_arrival) / mpg

        # Safety caps — never over-fill, never negative
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
            logger.debug(
                "Stop %d: %s, %s — %.2f gal @ $%.3f = $%.2f (mile %.1f)",
                len(stops), station["name"], station["state"],
                gallons, station["price"], cost, station["route_distance"],
            )

    return stops, round(total_cost, 2)
