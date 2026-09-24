"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from config.views import health, liveness

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api-auth/", include("rest_framework.urls")),
    path("healthz", liveness, name="liveness"),
    path("readyz", health, name="readiness"),
    path("api/v1/", include("apps.users.interfaces.urls")),
]
