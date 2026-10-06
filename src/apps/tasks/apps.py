"""Django application configuration for tasks."""

from django.apps import AppConfig


class TasksConfig(AppConfig):
    """Configure the tasks bounded context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasks"
    label = "tasks"
    verbose_name = "Tasks"
