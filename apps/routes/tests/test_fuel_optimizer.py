"""
Tests for the greedy fuel optimizer.

These are pure-Python unit tests — no DB or network required.
"""

import pytest

from apps.routes.services.fuel_optimizer import optimize_fuel_stops

MAX_RANGE = 500.0
MPG = 10.0


def make_station(route_distance: float, price: float, idx: int = 0) -> dict:
    return {
        "station_id": idx,
        "name": f"Station {idx}",
        "address": "",
        "city": "Testville",
        "state": "TX",
        "latitude": 30.0,
        "longitude": -97.0,
        "price": price,
        "route_distance": route_distance,
        "distance_from_route": 0.0,
    }


class TestOptimizeFuelStops:
    def test_no_stop_needed_short_trip(self):
        """Trip under 500 miles with no stations → no stops, $0."""
        stops, cost = optimize_fuel_stops([], 400.0, MAX_RANGE, MPG)
        assert stops == []
        assert cost == 0.0

    def test_single_mandatory_stop(self):
        """700-mile trip: must stop somewhere in the 500-mile window."""
        stations = [
            make_station(200.0, 3.00, 1),
            make_station(400.0, 3.50, 2),
            make_station(600.0, 2.80, 3),
        ]
        stops, cost = optimize_fuel_stops(stations, 700.0, MAX_RANGE, MPG)
        assert len(stops) >= 1
        assert cost > 0

    def test_prefers_cheaper_station(self):
        """Algorithm should bypass an expensive early station to reach a cheap one."""
        stations = [
            make_station(100.0, 5.00, 1),  # expensive, reachable
            make_station(300.0, 2.00, 2),  # cheap, also reachable
        ]
        stops, _ = optimize_fuel_stops(stations, 600.0, MAX_RANGE, MPG)
        stop_ids = [s["station_id"] for s in stops]
        # Station 2 (cheap) must appear; station 1 (expensive) should be skipped
        assert 2 in stop_ids

    def test_fills_up_when_all_ahead_are_expensive(self):
        """When everything ahead costs more, buy a full tank at the current stop."""
        stations = [
            make_station(100.0, 2.00, 1),  # cheapest
            make_station(400.0, 4.00, 2),  # expensive
            make_station(700.0, 4.50, 3),  # expensive
        ]
        stops, cost = optimize_fuel_stops(stations, 900.0, MAX_RANGE, MPG)
        # Should stop at station 1 and fill up
        assert stops[0]["station_id"] == 1
        # Buying a full tank at $2 is cheaper than partial fills at $4+
        assert cost < (900 / MPG) * 4.00

    def test_total_cost_correctness(self):
        """Manual trace: verify arithmetic matches the algorithm."""
        # 600-mile trip, stations at 300 ($3) and 500 ($4)
        # Start full (500 mi).  From 0: can reach both. Cheapest is 300 ($3).
        # From 300: dest at 600 is within 500 mi range → buy just enough.
        # Fuel on arrival at 300: 500 - 300 = 200 mi.  Need 300 mi to reach dest.
        # Buy (300 - 200)/10 = 10 gal at $3 = $30.
        stations = [make_station(300.0, 3.00, 1), make_station(500.0, 4.00, 2)]
        stops, cost = optimize_fuel_stops(stations, 600.0, MAX_RANGE, MPG)
        assert cost == pytest.approx(30.0, abs=0.01)
        assert len(stops) == 1

    def test_infeasible_raises(self):
        """No stations within range → ValueError."""
        with pytest.raises(ValueError):
            optimize_fuel_stops([], 1000.0, MAX_RANGE, MPG)
