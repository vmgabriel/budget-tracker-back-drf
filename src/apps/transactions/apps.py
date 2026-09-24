"""Django application configuration for transactions."""

from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    """Configure the transactions bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transactions"
    label = "transactions"
    verbose_name = "Transactions"
