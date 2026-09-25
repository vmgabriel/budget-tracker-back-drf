"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from config.schema import JWTAuthenticationScheme  # noqa: F401
from config.views import health, liveness

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", liveness, name="liveness"),
    path("readyz", health, name="readiness"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui-docs",
    ),
    path("api/v1/", include("apps.api.urls")),
]
