"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.tasks.infrastructure.persistence.models import (
    DailyPlanModel,
    GoalModel,
    TaskModel,
)

__all__ = (
    "DailyPlanModel",
    "GoalModel",
    "TaskModel",
)
