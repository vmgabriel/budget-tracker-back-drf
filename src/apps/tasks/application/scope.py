"""Owner-scoping helpers shared by tasks use cases.

A resource that does not exist and a resource owned by somebody else raise the
same ``*NotFound`` error on purpose: distinguishing them in the error message
would let an attacker probe which task identifiers exist.
"""

from uuid import UUID

from apps.tasks.application.ports.repositories import (
    DailyPlanRepository,
    GoalRepository,
    TaskRepository,
)
from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.exceptions import DailyPlanNotFound, GoalNotFound, TaskNotFound
from apps.tasks.domain.value_objects import DailyPlanId, GoalId, TaskId


def require_task_for_owner(
    tasks: TaskRepository, task_id: TaskId, user_id: UUID
) -> Task:
    """Return the task only when it exists and belongs to ``user_id``."""
    task = tasks.get_by_id(task_id)
    if task is None or task.user_id.value != user_id:
        raise TaskNotFound("Task not found.")
    return task


def require_goal_for_owner(
    goals: GoalRepository, goal_id: GoalId, user_id: UUID
) -> Goal:
    """Return the goal only when it exists and belongs to ``user_id``."""
    goal = goals.get_by_id(goal_id)
    if goal is None or goal.user_id.value != user_id:
        raise GoalNotFound("Goal not found.")
    return goal


def require_daily_plan_for_owner(
    plans: DailyPlanRepository, plan_id: DailyPlanId, user_id: UUID
) -> DailyPlan:
    """Return the daily plan only when it exists and belongs to ``user_id``."""
    plan = plans.get_by_id(plan_id)
    if plan is None or plan.user_id.value != user_id:
        raise DailyPlanNotFound("Daily plan not found.")
    return plan
