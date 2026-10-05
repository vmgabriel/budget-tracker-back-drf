"""Django application configuration for rentals."""

from django.apps import AppConfig


class RentalsConfig(AppConfig):
    """Configure the rentals bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rentals"
    label = "rentals"
    verbose_name = "Rentals"
