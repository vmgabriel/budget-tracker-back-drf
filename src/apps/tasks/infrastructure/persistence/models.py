"""Django ORM representations of the tasks aggregates."""

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.tasks.domain.value_objects import (
    GOAL_STATUS_CHOICES,
    PRIORITY_CHOICES,
    TASK_STATUS_CHOICES,
    GoalStatus,
    Priority,
    TaskStatus,
)

VALID_PRIORITIES = tuple(item.value for item in Priority)
VALID_TASK_STATUSES = tuple(item.value for item in TaskStatus)
VALID_GOAL_STATUSES = tuple(item.value for item in GoalStatus)

MAX_HOURS = 999999.99


class GoalModel(models.Model):
    """A macrotask grouping several tasks under a shared outcome."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="goals",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=GOAL_STATUS_CHOICES,
        default=GoalStatus.ACTIVE.value,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_GOAL_STATUSES),
                name="goal_valid_status",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="goal_name_nonblank",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status"), name="goal_owner_status_idx"),
            models.Index(fields=("user", "-due_date"), name="goal_owner_due_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class TaskModel(models.Model):
    """One owner-scoped unit of work, optionally part of a goal."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    goal = models.ForeignKey(
        GoalModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    due_date = models.DateField(null=True, blank=True)
    importance = models.CharField(
        max_length=8,
        choices=PRIORITY_CHOICES,
        default=Priority.MEDIUM.value,
    )
    estimated_hours = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    status = models.CharField(
        max_length=8,
        choices=TASK_STATUS_CHOICES,
        default=TaskStatus.TODO.value,
    )
    is_checked_by_llm = models.BooleanField(default=False)
    llm_evaluation_failed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(importance__in=VALID_PRIORITIES),
                name="task_valid_importance",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_TASK_STATUSES),
                name="task_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_hours__gte=0),
                name="task_hours_gte_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_hours__lte=MAX_HOURS),
                name="task_hours_lte_max",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "status"), name="task_owner_status_idx"),
            models.Index(fields=("user", "due_date"), name="task_owner_due_idx"),
            models.Index(fields=("goal",), name="task_goal_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class DailyPlanModel(models.Model):
    """The tasks scheduled for one owner on one calendar day."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_plans",
    )
    date = models.DateField()
    tasks = models.ManyToManyField(
        TaskModel,
        related_name="daily_plans",
        blank=True,
    )
    total_hours = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    generated_by_llm = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "date"),
                name="dailyplan_unique_user_date",
            ),
            models.CheckConstraint(
                condition=models.Q(total_hours__gte=0),
                name="dailyplan_hours_gte_zero",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "-date"), name="dailyplan_owner_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.date}: {self.total_hours}h"
