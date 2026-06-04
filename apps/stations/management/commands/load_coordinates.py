"""
Management command: load_coordinates
--------------------------------------
Populates station coordinates from the pre-built city-coordinate CSV
(data/fuel_city_coordinates.csv) instead of making thousands of API calls.

This is the FAST alternative to `geocode_stations`.

The CSV was generated from the GeoNames US dataset:
  city, state, latitude, longitude, source_name, population

3,805 city/state pairs covering the cities in the fuel-prices CSV.

Usage:
    python manage.py load_coordinates          # uses default CSV path
    python manage.py load_coordinates --csv path/to/other.csv
"""

import csv
import re
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.stations.models import FuelStation

DEFAULT_CSV = settings.BASE_DIR / "data" / "fuel_city_coordinates.csv"


def _normalize(value: str) -> str:
    text = (value or "").casefold().replace("&", " and ")
    text = re.sub(r"\bsaint\b", "st", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


class Command(BaseCommand):
    help = "Load station coordinates from the pre-built city-coordinates CSV (fast, no API calls)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default=str(DEFAULT_CSV),
            help="Path to the city coordinates CSV file.",
        )

    def handle(self, *args, **options) -> None:
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        self.stdout.write(f"Loading coordinates from {csv_path} …")
        t = time.monotonic()

        # Build lookup: (normalized_city, STATE) → (lat, lng)
        lookup: dict[tuple[str, str], tuple[float, float]] = {}
        with csv_path.open(encoding="utf-8-sig") as fh:
            for row in csv.DictReader(fh):
                city_key = _normalize(row["city"])
                state_key = row["state"].strip().upper()
                try:
                    lookup[(city_key, state_key)] = (
                        float(row["latitude"]),
                        float(row["longitude"]),
                    )
                except (ValueError, KeyError):
                    pass

        self.stdout.write(f"  Loaded {len(lookup)} city/state coordinate pairs.")

        # Match each station to its city entry
        updated = 0
        missed = 0
        now = timezone.now()

        # Process in batches to keep memory usage low
        batch: list[FuelStation] = []

        for station in FuelStation.objects.all().iterator(chunk_size=500):
            key = (_normalize(station.city), station.state.strip().upper())
            coords = lookup.get(key)
            if coords:
                station.latitude = coords[0]
                station.longitude = coords[1]
                station.geocoded_at = now
                batch.append(station)
                updated += 1
            else:
                missed += 1

            if len(batch) >= 500:
                FuelStation.objects.bulk_update(
                    batch, fields=["latitude", "longitude", "geocoded_at"]
                )
                batch.clear()
                self.stdout.write(f"  … {updated} updated", ending="\r")
                self.stdout.flush()

        if batch:
            FuelStation.objects.bulk_update(
                batch, fields=["latitude", "longitude", "geocoded_at"]
            )

        elapsed = time.monotonic() - t
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done in {elapsed:.1f}s — {updated} stations geocoded, {missed} unmatched."
            )
        )
        if missed:
            self.stdout.write(
                self.style.WARNING(
                    f"  {missed} stations had no city match in the CSV. "
                    "Run 'geocode_stations' to fill remaining gaps via Photon API."
                )
            )
