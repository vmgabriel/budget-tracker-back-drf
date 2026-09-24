"""Django application configuration for dashboard summaries."""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Configure the dashboard bounded context and transaction signals."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.dashboard"
    label = "dashboard"
    verbose_name = "Dashboard"

    def ready(self) -> None:
        """Register transaction lifecycle hooks after the app registry loads."""
        from apps.dashboard.infrastructure import signals  # noqa: F401
