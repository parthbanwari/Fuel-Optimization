"""
Management command: import_stations
------------------------------------
Loads (or refreshes) fuel station data from the OPIS CSV into the database.
Performs an upsert — existing rows are updated, new rows are inserted.

Usage:
    python manage.py import_stations
    python manage.py import_stations --csv path/to/other-file.csv
"""

import csv
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.stations.models import FuelStation

DEFAULT_CSV = settings.BASE_DIR / "data" / "fuel-prices-for-be-assessment.csv"


class Command(BaseCommand):
    help = "Import fuel stations from the OPIS CSV file (upsert)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            default=str(DEFAULT_CSV),
            help="Path to the fuel-prices CSV file.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Number of rows to bulk-upsert per DB round-trip.",
        )

    def handle(self, *args, **options) -> None:
        csv_path = Path(options["csv_path"])
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        self.stdout.write(f"Importing from {csv_path} …")
        start = time.monotonic()

        rows = self._parse_csv(csv_path)
        created, updated = self._upsert(rows, batch_size=options["batch_size"])

        elapsed = time.monotonic() - start
        self.stdout.write(
            self.style.SUCCESS(
                f"Done in {elapsed:.1f}s — {created} created, {updated} updated."
            )
        )

    # ── private helpers ───────────────────────────────────────────────────────

    def _parse_csv(self, path: Path) -> list[dict]:
        rows = []
        skipped = 0
        with path.open(encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            for lineno, row in enumerate(reader, start=2):
                try:
                    price = Decimal(row["Retail Price"].strip())
                    rows.append(
                        {
                            "opis_id": int(row["OPIS Truckstop ID"].strip()),
                            "name": row["Truckstop Name"].strip(),
                            "address": row["Address"].strip(),
                            "city": row["City"].strip(),
                            "state": row["State"].strip().upper(),
                            "rack_id": int(row["Rack ID"].strip()),
                            "retail_price": price,
                        }
                    )
                except (KeyError, ValueError, InvalidOperation) as exc:
                    self.stderr.write(f"  ⚠ Skipping line {lineno}: {exc}")
                    skipped += 1

        if skipped:
            self.stdout.write(self.style.WARNING(f"  Skipped {skipped} malformed rows."))
        return rows

    def _upsert(self, rows: list[dict], batch_size: int) -> tuple[int, int]:
        """
        Bulk upsert in two passes:
          1. Fetch all existing OPIS IDs (1 query).
          2. bulk_create new stations (1 query per batch).
          3. bulk_update changed stations (1 query per batch).
        Preserves existing lat/lng so geocode_stations isn't invalidated by a
        price refresh.
        """
        existing: dict[int, FuelStation] = {
            s.opis_id: s for s in FuelStation.objects.only(
                "id", "opis_id", "name", "address", "city", "state", "rack_id", "retail_price"
            )
        }

        to_create: list[FuelStation] = []
        to_update: list[FuelStation] = []
        update_fields = ["name", "address", "city", "state", "rack_id", "retail_price"]

        seen_ids: set[int] = set()
        for data in rows:
            opis_id = data["opis_id"]
            if opis_id in seen_ids:
                # Duplicate OPIS ID in the CSV — keep last value
                pass
            seen_ids.add(opis_id)

            if opis_id in existing:
                station = existing[opis_id]
                for field in update_fields:
                    setattr(station, field, data[field])
                to_update.append(station)
            else:
                to_create.append(FuelStation(**data))

        # Bulk create
        for i in range(0, len(to_create), batch_size):
            FuelStation.objects.bulk_create(
                to_create[i : i + batch_size], ignore_conflicts=False
            )

        # Bulk update
        for i in range(0, len(to_update), batch_size):
            FuelStation.objects.bulk_update(
                to_update[i : i + batch_size], fields=update_fields, batch_size=batch_size
            )

        return len(to_create), len(to_update)
