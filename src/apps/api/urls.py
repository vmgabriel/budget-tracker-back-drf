"""API v1 URL configuration - aggregates all app module URLs."""

from django.urls import include, path

app_name = "api_v1"

urlpatterns = [
    # Authentication is intentionally mounted at the API root for backward
    # compatibility: /api/v1/auth/... and /api/v1/users/...
    path("", include("apps.users.interfaces.urls")),
    path("transactions/", include("apps.transactions.interfaces.urls")),
    path("dashboard/", include("apps.dashboard.interfaces.urls")),
]
