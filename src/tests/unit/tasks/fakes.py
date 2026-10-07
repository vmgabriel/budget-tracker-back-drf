"""In-memory test doubles for tasks application ports."""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from apps.tasks.application.llm import (
    DailyPlanProposal,
    TaskDecomposition,
    TaskEvaluation,
)
from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.value_objects import (
    DailyPlanId,
    GoalId,
    TaskId,
    UserId,
)

FIXED_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


class FakeTaskRepository:
    """Store task aggregates in memory."""

    def __init__(self) -> None:
        self.tasks: dict[TaskId, Task] = {}

    def get_by_id(self, task_id: TaskId) -> Task | None:
        return self.tasks.get(task_id)

    def get_by_ids(self, task_ids: Sequence[TaskId]) -> list[Task]:
        return [self.tasks[task_id] for task_id in task_ids if task_id in self.tasks]

    def get_by_user_id(self, user_id: UserId) -> list[Task]:
        return [task for task in self.tasks.values() if task.user_id == user_id]

    def get_by_goal_id(self, goal_id: GoalId) -> list[Task]:
        return [task for task in self.tasks.values() if task.goal_id == goal_id]

    def save(self, task: Task) -> Task:
        if task.id is None:
            task.id = TaskId(uuid4())
        self.tasks[task.id] = task
        return task

    def update(self, task: Task) -> Task:
        if task.id is None:
            raise ValueError("Cannot update an unidentified task.")
        self.tasks[task.id] = task
        return task

    def delete(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("Cannot delete an unidentified task.")
        del self.tasks[task.id]


class FakeGoalRepository:
    """Store goal aggregates in memory."""

    def __init__(self) -> None:
        self.goals: dict[GoalId, Goal] = {}

    def get_by_id(self, goal_id: GoalId) -> Goal | None:
        return self.goals.get(goal_id)

    def get_by_user_id(self, user_id: UserId) -> list[Goal]:
        return [goal for goal in self.goals.values() if goal.user_id == user_id]

    def save(self, goal: Goal) -> Goal:
        if goal.id is None:
            goal.id = GoalId(uuid4())
        self.goals[goal.id] = goal
        return goal

    def update(self, goal: Goal) -> Goal:
        if goal.id is None:
            raise ValueError("Cannot update an unidentified goal.")
        self.goals[goal.id] = goal
        return goal

    def delete(self, goal: Goal) -> None:
        if goal.id is None:
            raise ValueError("Cannot delete an unidentified goal.")
        del self.goals[goal.id]


class FakeDailyPlanRepository:
    """Store daily plan aggregates in memory."""

    def __init__(self) -> None:
        self.plans: dict[DailyPlanId, DailyPlan] = {}

    def get_by_id(self, plan_id: DailyPlanId) -> DailyPlan | None:
        return self.plans.get(plan_id)

    def get_by_user_and_date(self, user_id: UserId, day: date) -> DailyPlan | None:
        for plan in self.plans.values():
            if plan.user_id == user_id and plan.date == day:
                return plan
        return None

    def get_by_user_and_date_range(
        self, user_id: UserId, start_date: date, end_date: date
    ) -> list[DailyPlan]:
        return [
            plan
            for plan in self.plans.values()
            if plan.user_id == user_id and start_date <= plan.date <= end_date
        ]

    def save(self, plan: DailyPlan) -> DailyPlan:
        if plan.id is None:
            plan.id = DailyPlanId(uuid4())
        self.plans[plan.id] = plan
        return plan

    def update(self, plan: DailyPlan) -> DailyPlan:
        if plan.id is None:
            raise ValueError("Cannot update an unidentified daily plan.")
        self.plans[plan.id] = plan
        return plan

    def delete(self, plan: DailyPlan) -> None:
        if plan.id is None:
            raise ValueError("Cannot delete an unidentified daily plan.")
        del self.plans[plan.id]


class FakeLlmAssistant:
    """Answer assistant calls from canned values, recording what was asked.

    ``failure`` stands in for every way a real provider can let us down: an
    unreachable daemon, an unparseable reply, and a provider raising something
    outside the port's own vocabulary all have to degrade the same way.
    """

    def __init__(
        self,
        evaluation: TaskEvaluation | None = None,
        decomposition: TaskDecomposition | None = None,
        plan: DailyPlanProposal | None = None,
        failure: Exception | None = None,
        available: bool = True,
    ) -> None:
        self.evaluation = evaluation
        self.decomposition = decomposition
        self.plan = plan
        self.failure = failure
        self.available = available
        self.evaluate_calls: list[dict[str, Any]] = []
        self.decompose_calls: list[dict[str, Any]] = []
        self.plan_calls: list[dict[str, Any]] = []

    def evaluate_task(
        self,
        *,
        name: str,
        description: str,
        due_date_iso: str | None,
    ) -> TaskEvaluation:
        self._raise_if_failing()
        self.evaluate_calls.append(
            {"name": name, "description": description, "due_date_iso": due_date_iso}
        )
        if self.evaluation is None:
            raise AssertionError("No evaluation was configured for this assistant.")
        return self.evaluation

    def decompose_task(self, *, name: str, description: str) -> TaskDecomposition:
        self._raise_if_failing()
        self.decompose_calls.append({"name": name, "description": description})
        if self.decomposition is None:
            raise AssertionError("No decomposition was configured for this assistant.")
        return self.decomposition

    def plan_day(
        self,
        *,
        date_iso: str,
        max_hours: str,
        candidates: tuple[tuple[TaskId, str, str, str, str | None], ...],
    ) -> DailyPlanProposal:
        self._raise_if_failing()
        self.plan_calls.append(
            {"date_iso": date_iso, "max_hours": max_hours, "candidates": candidates}
        )
        if self.plan is None:
            raise AssertionError("No plan was configured for this assistant.")
        return self.plan

    def is_available(self) -> bool:
        return self.available

    def _raise_if_failing(self) -> None:
        if self.failure is not None:
            raise self.failure
