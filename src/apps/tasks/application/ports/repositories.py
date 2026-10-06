"""Persistence ports for the tasks context.

Every method speaks domain types: identifiers as value objects and results as
aggregates. Implementations live in ``infrastructure`` and are the only place
allowed to know about Django.
"""

from collections.abc import Sequence
from datetime import date
from typing import Protocol

from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.value_objects import DailyPlanId, GoalId, TaskId, UserId


class TaskRepository(Protocol):
    """Storage operations required by task use cases."""

    def get_by_id(self, task_id: TaskId) -> Task | None:
        """Find a task by its identity."""
        ...

    def get_by_ids(self, task_ids: Sequence[TaskId]) -> list[Task]:
        """Return the tasks matching ``task_ids`` that exist."""
        ...

    def get_by_user_id(self, user_id: UserId) -> list[Task]:
        """Return every task owned by ``user_id``."""
        ...

    def get_by_goal_id(self, goal_id: GoalId) -> list[Task]:
        """Return every task linked to ``goal_id``."""
        ...

    def save(self, task: Task) -> Task:
        """Persist a new task and return its stored representation."""
        ...

    def update(self, task: Task) -> Task:
        """Persist changes made to an existing task."""
        ...

    def delete(self, task: Task) -> None:
        """Delete an existing task."""
        ...


class GoalRepository(Protocol):
    """Storage operations required by goal use cases."""

    def get_by_id(self, goal_id: GoalId) -> Goal | None:
        """Find a goal by its identity."""
        ...

    def get_by_user_id(self, user_id: UserId) -> list[Goal]:
        """Return every goal owned by ``user_id``."""
        ...

    def save(self, goal: Goal) -> Goal:
        """Persist a new goal and return its stored representation."""
        ...

    def update(self, goal: Goal) -> Goal:
        """Persist changes made to an existing goal."""
        ...

    def delete(self, goal: Goal) -> None:
        """Delete an existing goal."""
        ...


class DailyPlanRepository(Protocol):
    """Storage operations required by daily plan use cases."""

    def get_by_id(self, plan_id: DailyPlanId) -> DailyPlan | None:
        """Find a daily plan by its identity."""
        ...

    def get_by_user_and_date(self, user_id: UserId, day: date) -> DailyPlan | None:
        """Return the plan a user has for ``day``, when one exists."""
        ...

    def get_by_user_and_date_range(
        self, user_id: UserId, start_date: date, end_date: date
    ) -> list[DailyPlan]:
        """Return the plans a user has between two dates, inclusive."""
        ...

    def save(self, plan: DailyPlan) -> DailyPlan:
        """Persist a new daily plan and return its stored representation."""
        ...

    def update(self, plan: DailyPlan) -> DailyPlan:
        """Persist changes made to an existing daily plan."""
        ...

    def delete(self, plan: DailyPlan) -> None:
        """Delete an existing daily plan."""
        ...
