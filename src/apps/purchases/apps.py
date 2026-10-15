"""Django application configuration for purchases."""

from django.apps import AppConfig


class PurchasesConfig(AppConfig):
    """Configure the purchases bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.purchases"
    label = "purchases"
    verbose_name = "Purchases"

    def ready(self) -> None:
        """Import the Celery tasks so a worker registers them.

        ``autodiscover_tasks`` only scans for a ``tasks`` module directly under
        each installed app, and these live in ``infrastructure.tasks``. Without
        this import a worker boots with an empty registry for this context, and
        the nightly archival sweep silently never runs.
        """
        from apps.purchases.infrastructure import tasks as _tasks  # noqa: F401
