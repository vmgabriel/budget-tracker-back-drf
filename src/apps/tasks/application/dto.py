"""Application-layer representations safe to return from interfaces.

Entities expose value objects and behaviour; interfaces need plain, already
validated data. These DTOs are the only shapes the HTTP layer will serialize,
and they carry the derived flags (``is_overwhelmed``, ``task_count``,
``is_full``) that the domain deliberately computes per caller rather than
storing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.value_objects import (
    DailyPlanId,
    Duration,
    GoalId,
    GoalStatus,
    OverwhelmedThreshold,
    Priority,
    TaskId,
    TaskStatus,
    UserId,
)


@dataclass(frozen=True, slots=True)
class TaskDetails:
    """Task data safe to expose through an HTTP interface."""

    id: TaskId
    user_id: UserId
    goal_id: GoalId | None
    name: str
    description: str
    due_date: date | None
    importance: Priority
    estimated_hours: Decimal
    status: TaskStatus
    is_overwhelmed: bool
    is_checked_by_llm: bool
    llm_evaluation_failed: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class GoalDetails:
    """Goal data safe to expose through an HTTP interface."""

    id: GoalId
    user_id: UserId
    name: str
    description: str
    due_date: date | None
    status: GoalStatus
    task_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DailyPlanDetails:
    """Daily plan data safe to expose through an HTTP interface."""

    id: DailyPlanId
    user_id: UserId
    date: date
    tasks: tuple[TaskDetails, ...]
    total_hours: Decimal
    is_full: bool
    generated_by_llm: bool
    created_at: datetime


def task_details(task: Task, threshold: OverwhelmedThreshold) -> TaskDetails:
    """Convert a persisted task into a safe result."""
    if task.id is None:
        raise ValueError("A persisted task must have an identity.")
    return TaskDetails(
        id=task.id,
        user_id=task.user_id,
        goal_id=task.goal_id,
        name=task.name,
        description=task.description,
        due_date=task.due_date,
        importance=task.importance,
        estimated_hours=task.estimated_hours.hours,
        status=task.status,
        is_overwhelmed=task.is_overwhelmed(threshold),
        is_checked_by_llm=task.is_checked_by_llm,
        llm_evaluation_failed=task.llm_evaluation_failed,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def goal_details(goal: Goal, task_count: int = 0) -> GoalDetails:
    """Convert a persisted goal into a safe result."""
    if goal.id is None:
        raise ValueError("A persisted goal must have an identity.")
    return GoalDetails(
        id=goal.id,
        user_id=goal.user_id,
        name=goal.name,
        description=goal.description,
        due_date=goal.due_date,
        status=goal.status,
        task_count=task_count,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def ordered_tasks(plan: DailyPlan, tasks: Sequence[Task]) -> tuple[Task, ...]:
    """Return the given tasks in the order the plan schedules them.

    Storage may return them in any order, but a day reads as a sequence, so the
    plan decides the order. Tasks that no longer exist are skipped instead of
    raising: one deleted task must not break the whole day view.
    """
    found = {task.id: task for task in tasks if task.id is not None}
    return tuple(found[task_id] for task_id in plan.task_ids if task_id in found)


def daily_plan_details(
    plan: DailyPlan,
    tasks: Sequence[Task],
    threshold: OverwhelmedThreshold,
    max_hours: Duration,
) -> DailyPlanDetails:
    """Convert a persisted daily plan and its tasks into a safe result."""
    if plan.id is None:
        raise ValueError("A persisted daily plan must have an identity.")
    return DailyPlanDetails(
        id=plan.id,
        user_id=plan.user_id,
        date=plan.date,
        tasks=tuple(task_details(task, threshold) for task in tasks),
        total_hours=plan.total_hours.hours,
        is_full=plan.is_full(max_hours),
        generated_by_llm=plan.generated_by_llm,
        created_at=plan.created_at,
    )
