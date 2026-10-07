"""Django application configuration for tasks."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Configure the tasks bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks"

    def ready(self) -> None:
        """Import the Celery tasks so a worker registers them.

        ``autodiscover_tasks`` scans for a ``tasks`` module directly under each
        installed app, and these live in ``infrastructure.tasks`` instead.
        Something has to import them, or a worker boots with an empty registry
        for this context.

        The failure is silent and asymmetric: the web process reaches these
        tasks through the views, so it sees a healthy registry the worker never
        gets. Requests queue messages nobody consumes.
        """
        from apps.tasks.infrastructure import tasks as _tasks  # noqa: F401
