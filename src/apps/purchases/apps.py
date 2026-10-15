"""Django application configuration for purchases."""

from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    """Configure the purchases bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchases"
    label = "purchases"
    verbose_name = "Purchases"
