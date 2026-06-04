from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    """Input: origin and destination as plain text (city, state or full address)."""

    origin = serializers.CharField(
        max_length=255,
        help_text='Starting location within the USA, e.g. "New York, NY"',
    )
    destination = serializers.CharField(
        max_length=255,
        help_text='Ending location within the USA, e.g. "Los Angeles, CA"',
    )

    def validate_origin(self, value: str) -> str:
        return value.strip()

    def validate_destination(self, value: str) -> str:
        return value.strip()

    def validate(self, attrs: dict) -> dict:
        if attrs["origin"].lower() == attrs["destination"].lower():
            raise serializers.ValidationError("Origin and destination must be different.")
        return attrs


# ── Response serializers (for OpenAPI schema generation) ─────────────────────

class CoordinateSerializer(serializers.Serializer):
    input = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class RouteGeometrySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    total_duration_hours = serializers.FloatField(help_text="Decimal hours, e.g. 19.78")
    total_duration_human = serializers.CharField(help_text="Human-readable, e.g. '19h 46m'")
    geometry = serializers.DictField(help_text="GeoJSON LineString geometry of the route")


class FuelStopSerializer(serializers.Serializer):
    stop_number = serializers.IntegerField()
    station_id = serializers.IntegerField()
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    distance_from_route_miles = serializers.FloatField()
    route_distance_miles = serializers.FloatField()
    price_per_gallon = serializers.FloatField()
    gallons_purchased = serializers.FloatField()
    cost_at_stop = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    total_fuel_cost_usd = serializers.FloatField()
    total_gallons_purchased = serializers.FloatField()
    num_stops = serializers.IntegerField()
    avg_price_per_gallon = serializers.FloatField()


class RouteMetaSerializer(serializers.Serializer):
    cached = serializers.BooleanField()
    response_time_ms = serializers.IntegerField()
    stations_evaluated = serializers.IntegerField()
    corridor_miles = serializers.IntegerField()
    vehicle_range_miles = serializers.IntegerField()
    vehicle_mpg = serializers.IntegerField()


class RouteResponseSerializer(serializers.Serializer):
    origin = CoordinateSerializer()
    destination = CoordinateSerializer()
    route = RouteGeometrySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    summary = RouteSummarySerializer()
    meta = RouteMetaSerializer()
