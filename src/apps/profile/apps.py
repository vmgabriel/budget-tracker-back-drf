"""Django application configuration for profiles."""

from django.apps import AppConfig


class ProfileConfig(AppConfig):
    """Configure the profile bounded context and user lifecycle signals."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.profile"
    label = "profile"
    verbose_name = "Profile"

    def ready(self) -> None:
        """Register user lifecycle hooks after the app registry loads."""
        from apps.profile.infrastructure import signals  # noqa: F401
