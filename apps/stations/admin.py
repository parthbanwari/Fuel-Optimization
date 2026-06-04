from django.contrib import admin

from .models import FuelStation


@admin.register(FuelStation)
class FuelStationAdmin(admin.ModelAdmin):
    list_display = ("opis_id", "name", "city", "state", "retail_price", "is_geocoded")
    list_filter = ("state",)
    search_fields = ("name", "city", "address")
    readonly_fields = ("geocoded_at",)

    @admin.display(boolean=True, description="Geocoded?")
    def is_geocoded(self, obj: FuelStation) -> bool:
        return obj.is_geocoded
