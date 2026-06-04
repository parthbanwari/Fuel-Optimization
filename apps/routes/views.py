import logging

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RouteRequestSerializer, RouteResponseSerializer
from .services.route_service import RouteServiceError, plan_route

logger = logging.getLogger(__name__)


class RouteView(APIView):
    """
    POST /api/v1/routes/

    Given a US origin and destination, returns:
    • The driving route geometry (GeoJSON LineString)
    • Optimal fuel stops based on current truck-stop prices
    • Total money spent on fuel
    """

    @extend_schema(
        request=RouteRequestSerializer,
        responses={200: RouteResponseSerializer},
        summary="Plan a fuel-optimised route",
        description=(
            "Returns the driving route between two US locations along with the "
            "cheapest set of fuel stops (respecting a 500-mile vehicle range) "
            "and the total estimated fuel cost."
        ),
    )
    def post(self, request: Request) -> Response:
        serializer = RouteRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        origin = serializer.validated_data["origin"]
        destination = serializer.validated_data["destination"]

        try:
            result = plan_route(origin, destination)
        except RouteServiceError as exc:
            http_status = exc.status if hasattr(exc, "status") else 400
            return Response({"error": str(exc)}, status=http_status)
        except Exception as exc:
            logger.exception("Unexpected error planning route %s → %s", origin, destination)
            return Response(
                {"error": "An unexpected error occurred. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_200_OK)


class HealthView(APIView):
    """GET /api/v1/health/ — liveness probe."""

    @extend_schema(exclude=True)
    def get(self, request: Request) -> Response:
        from apps.stations.models import FuelStation
        station_count = FuelStation.objects.count()
        geocoded_count = FuelStation.objects.filter(latitude__isnull=False).count()
        return Response(
            {
                "status": "ok",
                "stations_total": station_count,
                "stations_geocoded": geocoded_count,
            }
        )
