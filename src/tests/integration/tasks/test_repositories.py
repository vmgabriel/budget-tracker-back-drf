"""Django ORM adapter tests for the tasks context."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from django.db import IntegrityError

from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.exceptions import TaskNotFound
from apps.tasks.domain.value_objects import (
    Duration,
    GoalStatus,
    Priority,
    TaskStatus,
    UserId,
)
from apps.tasks.infrastructure.persistence.models import (
    DailyPlanModel,
    GoalModel,
    TaskModel,
)
from apps.tasks.infrastructure.persistence.repositories import (
    DjangoDailyPlanRepository,
    DjangoGoalRepository,
    DjangoTaskRepository,
)
from tests.factories import DailyPlanFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


def _identities(entities: list[Any]) -> list[UUID]:
    """Return the identifiers of the given aggregates.

    Aggregates are compared by identity on purpose (``eq=False``), so tests
    assert on identities instead of relying on structural equality.
    """
    return [entity.id.value for entity in entities]


def _goal(user: Any, name: str = "Spring cleaning") -> Goal:
    return Goal.create(
        user_id=UserId(user.id),
        name=name,
        description="Deep clean",
        due_date=date(2026, 2, 1),
        now=NOW,
    )


def _task(
    user: Any,
    goal: Goal | None = None,
    *,
    name: str = "Water the plants",
    hours: str = "1.50",
    due_date: date | None = date(2026, 1, 20),
) -> Task:
    return Task.create(
        user_id=UserId(user.id),
        goal_id=goal.id if goal is not None else None,
        name=name,
        description="Every three days",
        importance=Priority.MEDIUM,
        estimated_hours=Duration(Decimal(hours)),
        due_date=due_date,
        now=NOW,
    )


def test_goal_repository_round_trips_every_field() -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    repository = DjangoGoalRepository()

    saved = repository.save(_goal(owner))

    assert saved.id is not None
    assert saved.user_id == UserId(owner.id)
    assert saved.name == "Spring cleaning"
    assert saved.description == "Deep clean"
    assert saved.due_date == date(2026, 2, 1)
    assert saved.status is GoalStatus.ACTIVE

    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.name == saved.name
    assert loaded.description == saved.description
    assert loaded.due_date == saved.due_date
    assert loaded.status is saved.status
    assert loaded.created_at == saved.created_at
    assert _identities(repository.get_by_user_id(UserId(owner.id))) == [loaded.id.value]
    assert repository.get_by_user_id(UserId(other.id)) == []


def test_goal_repository_update_and_delete() -> None:
    owner: Any = UserFactory()
    repository = DjangoGoalRepository()
    goal = repository.save(_goal(owner))
    assert goal.id is not None

    goal.update(
        name="Autumn cleaning",
        description="Leaves",
        due_date=None,
        now=datetime(2026, 1, 16, 9, tzinfo=UTC),
    )
    goal.mark_as_completed(now=datetime(2026, 1, 16, 9, tzinfo=UTC))

    updated = repository.update(goal)

    assert updated.name == "Autumn cleaning"
    assert updated.description == "Leaves"
    assert updated.due_date is None
    assert updated.status is GoalStatus.COMPLETED
    assert GoalModel.objects.get(pk=goal.id.value).status == GoalStatus.COMPLETED.value

    repository.delete(updated)
    assert repository.get_by_id(goal.id) is None


def test_task_repository_round_trips_and_scopes_lookups() -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    goals = DjangoGoalRepository()
    repository = DjangoTaskRepository()
    goal = goals.save(_goal(owner))
    assert goal.id is not None

    saved = repository.save(_task(owner, goal))

    assert saved.id is not None
    assert saved.user_id == UserId(owner.id)
    assert saved.goal_id == goal.id
    assert saved.name == "Water the plants"
    assert saved.description == "Every three days"
    assert saved.due_date == date(2026, 1, 20)
    assert saved.importance is Priority.MEDIUM
    assert saved.estimated_hours == Duration(Decimal("1.50"))
    assert saved.status is TaskStatus.TODO
    assert saved.is_checked_by_llm is False
    assert saved.llm_evaluation_failed is False

    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.goal_id == saved.goal_id
    assert loaded.description == saved.description
    assert loaded.importance is saved.importance
    assert loaded.estimated_hours == saved.estimated_hours
    assert loaded.status is saved.status
    assert loaded.created_at == saved.created_at
    assert _identities(repository.get_by_ids([saved.id])) == [loaded.id.value]
    assert repository.get_by_ids([]) == []
    assert _identities(repository.get_by_goal_id(goal.id)) == [loaded.id.value]
    assert _identities(repository.get_by_user_id(UserId(owner.id))) == [loaded.id.value]
    assert repository.get_by_user_id(UserId(other.id)) == []


def test_task_repository_update_writes_every_mutable_field() -> None:
    owner: Any = UserFactory()
    goals = DjangoGoalRepository()
    repository = DjangoTaskRepository()
    goal = goals.save(_goal(owner))
    assert goal.id is not None
    task = repository.save(_task(owner))
    assert task.id is not None
    later = datetime(2026, 1, 16, 9, tzinfo=UTC)

    task.update(
        name="  Repaint the fence  ",
        description="Two coats",
        importance=Priority.HIGH,
        estimated_hours=Duration(Decimal("6.00")),
        due_date=None,
        now=later,
    )
    task.link_to_goal(goal.id, now=later)
    task.mark_as_done(now=later)
    task.mark_llm_checked()

    updated = repository.update(task)

    assert updated.name == "Repaint the fence"
    assert updated.description == "Two coats"
    assert updated.importance is Priority.HIGH
    assert updated.estimated_hours == Duration(Decimal("6.00"))
    assert updated.due_date is None
    assert updated.goal_id == goal.id
    assert updated.status is TaskStatus.DONE
    assert updated.is_checked_by_llm is True


def test_task_repository_omits_absent_due_date_and_clears_it_on_demand() -> None:
    """``UNSET`` and ``None`` look identical at the ORM boundary.

    Partial-update semantics are resolved before persistence: a use case that
    leaves a field alone copies the stored value into the aggregate, and one
    that clears it writes ``None``. Either way the row ends up with exactly
    what the aggregate holds, which is what this test pins down.
    """
    owner: Any = UserFactory()
    repository = DjangoTaskRepository()
    task = repository.save(_task(owner, due_date=date(2026, 1, 20)))
    assert task.id is not None

    # Untouched field: the aggregate keeps the stored deadline.
    unchanged = repository.update(task)
    assert unchanged.due_date == date(2026, 1, 20)

    # Cleared field: the aggregate carries None and the column follows.
    unchanged.due_date = None
    cleared = repository.update(unchanged)
    assert cleared.due_date is None
    reloaded = repository.get_by_id(task.id)
    assert reloaded is not None
    assert reloaded.due_date is None

    # And the deadline can be set again afterwards.
    reloaded.due_date = date(2026, 3, 1)
    assert repository.update(reloaded).due_date == date(2026, 3, 1)


def test_task_repository_rejects_rows_deleted_behind_its_back() -> None:
    owner: Any = UserFactory()
    repository = DjangoTaskRepository()
    task = repository.save(_task(owner))
    assert task.id is not None
    TaskModel.objects.filter(pk=task.id.value).delete()

    with pytest.raises(TaskNotFound):
        repository.update(task)
    with pytest.raises(TaskNotFound):
        repository.delete(task)


def test_task_repository_refuses_unidentified_aggregates() -> None:
    owner: Any = UserFactory()
    repository = DjangoTaskRepository()
    unsaved = _task(owner)

    with pytest.raises(ValueError, match="identity"):
        repository.update(unsaved)
    with pytest.raises(ValueError, match="identity"):
        repository.delete(unsaved)


def test_deleting_a_goal_keeps_its_tasks() -> None:
    owner: Any = UserFactory()
    goals = DjangoGoalRepository()
    tasks = DjangoTaskRepository()
    goal = goals.save(_goal(owner))
    task = tasks.save(_task(owner, goal))
    assert task.id is not None

    goal_id = goal.id
    assert goal_id is not None
    goals.delete(goal)

    stored = tasks.get_by_id(task.id)
    assert stored is not None
    assert stored.goal_id is None
    assert tasks.get_by_goal_id(goal_id) == []


def test_daily_plan_repository_round_trips_scheduled_tasks() -> None:
    owner: Any = UserFactory()
    tasks = DjangoTaskRepository()
    repository = DjangoDailyPlanRepository()
    first = tasks.save(_task(owner, name="First", hours="1.00"))
    second = tasks.save(_task(owner, name="Second", hours="2.00"))
    assert first.id is not None
    assert second.id is not None
    plan = DailyPlan.create(
        user_id=UserId(owner.id),
        date=date(2026, 1, 15),
        now=NOW,
    )

    saved = repository.save(plan)
    assert saved.id is not None
    assert saved.total_hours == Duration(Decimal("0.00"))
    assert saved.task_ids == []

    # Load, mutate, persist: the aggregate only gains an identity through a
    # repository call, exactly like a use case would do it.
    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    loaded.add_task(first.id, first.estimated_hours)
    loaded.add_task(second.id, second.estimated_hours)
    loaded.mark_as_llm_generated()

    updated = repository.update(loaded)

    assert updated.total_hours == Duration(Decimal("3.00"))
    assert updated.generated_by_llm is True
    assert set(updated.task_ids) == {first.id, second.id}

    reloaded = repository.get_by_id(saved.id)
    assert reloaded is not None
    assert reloaded.total_hours == Duration(Decimal("3.00"))
    assert set(reloaded.task_ids) == {first.id, second.id}
    assert reloaded.generated_by_llm is True

    same_day = repository.get_by_user_and_date(UserId(owner.id), date(2026, 1, 15))
    assert same_day is not None
    assert same_day.id == reloaded.id
    assert repository.get_by_user_and_date(UserId(owner.id), date(2026, 1, 16)) is None


def test_daily_plan_repository_lists_an_inclusive_range() -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    repository = DjangoDailyPlanRepository()
    for day in (date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 16)):
        repository.save(DailyPlan.create(user_id=UserId(owner.id), date=day, now=NOW))
    repository.save(
        DailyPlan.create(user_id=UserId(other.id), date=date(2026, 1, 15), now=NOW)
    )

    listed = repository.get_by_user_and_date_range(
        UserId(owner.id), date(2026, 1, 14), date(2026, 1, 15)
    )

    assert {plan.date for plan in listed} == {date(2026, 1, 14), date(2026, 1, 15)}


def test_daily_plan_delete_keeps_the_tasks_themselves() -> None:
    owner: Any = UserFactory()
    tasks = DjangoTaskRepository()
    repository = DjangoDailyPlanRepository()
    task = tasks.save(_task(owner))
    assert task.id is not None
    saved = repository.save(
        DailyPlan.create(user_id=UserId(owner.id), date=date(2026, 1, 15), now=NOW)
    )
    assert saved.id is not None
    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    loaded.add_task(task.id, task.estimated_hours)
    updated = repository.update(loaded)

    repository.delete(updated)

    assert repository.get_by_id(saved.id) is None
    assert tasks.get_by_id(task.id) is not None
    assert not DailyPlanModel.objects.filter(pk=saved.id.value).exists()


def test_one_plan_per_user_and_day_is_enforced_by_the_database() -> None:
    owner: Any = UserFactory()
    DailyPlanFactory(user=owner, date=date(2026, 1, 15))

    with pytest.raises(IntegrityError):
        DailyPlanModel.objects.create(
            user_id=owner.id,
            date=date(2026, 1, 15),
            total_hours=Decimal("0.00"),
            generated_by_llm=False,
        )


def test_lookups_never_cross_owner_boundaries() -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    repository = DjangoGoalRepository()
    goal = repository.save(_goal(owner))
    assert goal.id is not None

    assert repository.get_by_user_id(UserId(other.id)) == []
    assert GoalModel.objects.filter(pk=goal.id.value, user_id=other.id).count() == 0
