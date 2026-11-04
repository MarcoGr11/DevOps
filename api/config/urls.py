from django.contrib import admin
from django.urls import include, path

from booking.metrics_middleware import metrics_view
from booking.views import HealthCheckView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("metrics", metrics_view, name="metrics"),
    path("api/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/", include("booking.urls")),
]
