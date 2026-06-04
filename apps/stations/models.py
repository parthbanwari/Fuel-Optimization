from django.db import models


class FuelStation(models.Model):
    """
    A truck-stop fuel station loaded from the OPIS dataset.

    Coordinates are populated by the `geocode_stations` management command
    and are required for the station to appear in route results.
    """

    opis_id = models.IntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=2, db_index=True)
    rack_id = models.IntegerField()
    retail_price = models.DecimalField(max_digits=8, decimal_places=5)

    # Populated by `geocode_stations` management command
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    geocoded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["state", "city", "name"]
        indexes = [
            # Composite index for bounding-box queries in the spatial service
            models.Index(fields=["latitude", "longitude"], name="station_latlon_idx"),
        ]
        verbose_name = "Fuel Station"
        verbose_name_plural = "Fuel Stations"

    def __str__(self) -> str:
        return f"{self.name} — {self.city}, {self.state} (${self.retail_price:.3f})"

    @property
    def is_geocoded(self) -> bool:
        return self.latitude is not None and self.longitude is not None
