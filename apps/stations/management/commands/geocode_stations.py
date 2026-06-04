"""
Management command: geocode_stations
--------------------------------------
Resolves latitude/longitude for every FuelStation that lacks coordinates.

Strategy
--------
• Groups stations by (city, state) — there are far fewer unique city+state
  pairs than the 8 000+ total rows, so Nominatim is called only once per pair.
• Nominatim is free and requires no API key, but enforces 1 req/s.
  The RateLimiter wrapper in geopy handles this automatically.
• Results are cached in the DB; re-running the command is safe and cheap.

Usage:
    python manage.py geocode_stations          # only un-geocoded stations
    python manage.py geocode_stations --force  # re-geocode all stations
"""

import time
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.stations.models import FuelStation


class Command(BaseCommand):
    help = "Geocode fuel stations using Nominatim (groups by city/state)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-geocode stations that already have coordinates.",
        )
        parser.add_argument(
            "--state",
            dest="state",
            default=None,
            help="Only geocode stations in this state (e.g. TX).",
        )

    def handle(self, *args, **options) -> None:
        try:
            from geopy.extra.rate_limiter import RateLimiter
            from geopy.geocoders import Photon
        except ImportError:
            self.stderr.write(self.style.ERROR("geopy is not installed. Run: pip install geopy"))
            return

        qs = FuelStation.objects.all()
        if options["state"]:
            qs = qs.filter(state=options["state"].upper())
        if not options["force"]:
            qs = qs.filter(latitude__isnull=True)

        total = qs.count()
        if total == 0:
            self.stdout.write("All stations already geocoded. Use --force to redo.")
            return

        self.stdout.write(f"Geocoding {total} stations …")

        # Group station IDs by (city, state) to minimise API calls
        city_state_map: dict[tuple[str, str], list[int]] = defaultdict(list)
        for station in qs.only("id", "city", "state"):
            city_state_map[(station.city.strip(), station.state.strip())].append(station.id)

        # Photon (photon.komoot.io) uses the same OSM data as Nominatim but is
        # more permissive for scripted/bulk usage — no API key required.
        geolocator = Photon(user_agent="fuel_route_api", timeout=10)
        geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.1, error_wait_seconds=10)

        geocoded = 0
        failed = 0
        start = time.monotonic()

        for (city, state), ids in city_state_map.items():
            query = f"{city}, {state}, USA"
            try:
                location = geocode(query)  # ", USA" suffix is enough to bias results
            except Exception as exc:
                self.stderr.write(f"  ✗ {query}: {exc}")
                failed += len(ids)
                continue

            if location is None:
                self.stderr.write(f"  ✗ Not found: {query}")
                failed += len(ids)
                continue

            FuelStation.objects.filter(id__in=ids).update(
                latitude=location.latitude,
                longitude=location.longitude,
                geocoded_at=timezone.now(),
            )
            geocoded += len(ids)

            elapsed = time.monotonic() - start
            self.stdout.write(
                f"  ✓ {query} → ({location.latitude:.4f}, {location.longitude:.4f})"
                f"  [{geocoded}/{total} in {elapsed:.0f}s]",
                ending="\r",
            )
            self.stdout.flush()

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Done — {geocoded} geocoded, {failed} failed.")
        )
