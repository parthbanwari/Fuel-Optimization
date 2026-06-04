from django.urls import path

from .views import HealthView, RouteView

app_name = "routes"

urlpatterns = [
    path("routes/", RouteView.as_view(), name="plan-route"),
    path("health/", HealthView.as_view(), name="health"),
]
