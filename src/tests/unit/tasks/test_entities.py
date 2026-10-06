"""Tasks entity business-rule tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.exceptions import (
    DailyPlanFull,
    DailyPlanNotFound,
    TaskAlreadyDone,
    TaskAlreadyInPlan,
)
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

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 5, 12, tzinfo=UTC)
LATER = datetime(2026, 1, 6, 9, tzinfo=UTC)


def _task(**overrides: object) -> Task:
    payload: dict[str, object] = {
        "user_id": UserId(uuid4()),
        "name": "  Change the bed linen  ",
        "description": "## Steps\n- strip",
        "importance": Priority.MEDIUM,
        "estimated_hours": Duration(Decimal("1.5")),
        "now": NOW,
    }
    payload.update(overrides)
    return Task.create(**payload)  # type: ignore[arg-type]


def _goal(**overrides: object) -> Goal:
    payload: dict[str, object] = {
        "user_id": UserId(uuid4()),
        "name": "  Spring cleaning  ",
        "description": "Deep clean",
        "now": NOW,
    }
    payload.update(overrides)
    return Goal.create(**payload)  # type: ignore[arg-type]


def _plan(**overrides: object) -> DailyPlan:
    payload: dict[str, object] = {
        "user_id": UserId(uuid4()),
        "date": date(2026, 1, 5),
        "now": NOW,
    }
    payload.update(overrides)
    return DailyPlan.create(**payload)  # type: ignore[arg-type]


def test_task_create_normalizes_and_defaults() -> None:
    task = _task()

    assert task.name == "Change the bed linen"
    assert task.description == "## Steps\n- strip"
    assert task.id is None
    assert task.status is TaskStatus.TODO
    assert task.goal_id is None
    assert task.due_date is None
    assert task.is_checked_by_llm is False
    assert task.llm_evaluation_failed is False
    assert task.created_at == NOW
    assert task.updated_at == NOW


def test_task_create_rejects_invalid_input() -> None:
    with pytest.raises(TypeError, match="owner"):
        _task(user_id=uuid4())
    with pytest.raises(ValueError, match="importance"):
        _task(importance="high")
    with pytest.raises(TypeError, match="Duration"):
        _task(estimated_hours=Decimal("1.5"))
    with pytest.raises(ValueError, match="name cannot be empty"):
        _task(name="   ")
    with pytest.raises(ValueError, match="200 characters"):
        _task(name="x" * 201)
    with pytest.raises(ValueError, match="5000 characters"):
        _task(description="x" * 5001)
    with pytest.raises(ValueError, match="must be a date"):
        _task(due_date=NOW)
    with pytest.raises(ValueError, match="timezone-aware"):
        _task(now=datetime(2026, 1, 5, 12))


def test_task_is_overwhelmed_uses_caller_threshold() -> None:
    task = _task(estimated_hours=Duration(Decimal("4.00")))

    assert not task.is_overwhelmed(OverwhelmedThreshold(Decimal("4.0")))
    assert task.is_overwhelmed(OverwhelmedThreshold(Decimal("3.99")))
    with pytest.raises(TypeError):
        task.is_overwhelmed(Decimal("4"))  # type: ignore[arg-type]


def test_task_status_transitions() -> None:
    task = _task()

    task.mark_as_doing(now=LATER)
    assert task.status is TaskStatus.DOING
    assert task.updated_at == LATER

    task.mark_as_done(now=LATER)
    assert task.status is TaskStatus.DONE

    with pytest.raises(TaskAlreadyDone):
        task.mark_as_done(now=LATER)
    with pytest.raises(TaskAlreadyDone):
        task.mark_as_doing(now=LATER)


def test_task_promote_priority_saturates_at_high() -> None:
    task = _task(importance=Priority.LOW)

    assert task.promote_priority(now=LATER) is Priority.MEDIUM
    assert task.promote_priority(now=LATER) is Priority.HIGH
    assert task.promote_priority(now=LATER) is Priority.HIGH
    assert task.importance is Priority.HIGH
    assert task.updated_at == LATER


def test_task_goal_linkage() -> None:
    task = _task()
    goal_id = GoalId(uuid4())

    task.link_to_goal(goal_id, now=LATER)
    assert task.goal_id == goal_id

    task.unlink_from_goal(now=LATER)
    assert task.goal_id is None

    with pytest.raises(TypeError):
        task.link_to_goal(uuid4(), now=LATER)


def test_task_update_resets_llm_flag_only_on_content_change() -> None:
    task = _task()
    task.mark_llm_checked()

    task.update(
        name=task.name,
        description=task.description,
        due_date=task.due_date,
        importance=Priority.LOW,
        estimated_hours=Duration(Decimal("2.00")),
        now=LATER,
    )
    assert task.is_checked_by_llm is True
    assert task.importance is Priority.LOW
    assert task.estimated_hours == Duration(Decimal("2.00"))

    task.update(
        name="New name",
        description=task.description,
        due_date=task.due_date,
        importance=Priority.LOW,
        estimated_hours=Duration(Decimal("2.00")),
        now=LATER,
    )
    assert task.is_checked_by_llm is False
    assert task.needs_llm_evaluation is True


def test_task_llm_evaluation_flags() -> None:
    task = _task()

    assert task.needs_llm_evaluation is True

    task.mark_llm_checked()
    assert task.is_checked_by_llm is True
    assert task.needs_llm_evaluation is False

    task.flag_llm_evaluation_failed()
    assert task.llm_evaluation_failed is True
    assert task.needs_llm_evaluation is True


def test_goal_create_and_status_transitions() -> None:
    goal = _goal(due_date=date(2026, 2, 1))

    assert goal.name == "Spring cleaning"
    assert goal.status is GoalStatus.ACTIVE
    assert goal.due_date == date(2026, 2, 1)

    goal.mark_as_completed(now=LATER)
    assert goal.status is GoalStatus.COMPLETED

    goal.reactivate(now=LATER)
    assert goal.status is GoalStatus.ACTIVE

    goal.mark_as_archived(now=LATER)
    assert goal.status is GoalStatus.ARCHIVED


def test_goal_update_validates_fields() -> None:
    goal = _goal()

    goal.update(
        name="  Autumn cleaning  ",
        description="  Leaves  ",
        due_date=date(2026, 3, 1),
        now=LATER,
    )
    assert goal.name == "Autumn cleaning"
    assert goal.description == "Leaves"
    assert goal.due_date == date(2026, 3, 1)
    assert goal.updated_at == LATER

    with pytest.raises(ValueError, match="Goal name cannot be empty"):
        goal.update(name="  ", description="", due_date=None, now=LATER)
    with pytest.raises(ValueError, match="Goal due date must be a date"):
        goal.update(name="Valid", description="", due_date=NOW, now=LATER)


def test_daily_plan_create_defaults() -> None:
    plan = _plan()

    assert plan.id is None
    assert plan.task_ids == []
    assert plan.total_hours == Duration(Decimal("0"))
    assert plan.generated_by_llm is False
    assert plan.contains(TaskId(uuid4())) is False


def test_daily_plan_create_rejects_invalid_input() -> None:
    with pytest.raises(TypeError, match="owner"):
        _plan(user_id=uuid4())
    with pytest.raises(ValueError, match="must be a date"):
        _plan(date=None)
    with pytest.raises(ValueError, match="timezone-aware"):
        _plan(now=datetime(2026, 1, 5, 12))


def test_daily_plan_adds_and_removes_tasks() -> None:
    plan = _plan()
    task_id = TaskId(uuid4())

    plan.add_task(task_id, Duration(Decimal("2.00")))
    assert plan.contains(task_id) is True
    assert plan.total_hours == Duration(Decimal("2.00"))

    with pytest.raises(TaskAlreadyInPlan):
        plan.add_task(task_id, Duration(Decimal("2.00")))

    plan.remove_task(task_id, Duration(Decimal("2.00")))
    assert plan.contains(task_id) is False
    assert plan.total_hours == Duration(Decimal("0"))


def test_daily_plan_remove_unknown_task() -> None:
    plan = _plan()

    with pytest.raises(DailyPlanNotFound):
        plan.remove_task(TaskId(uuid4()), Duration(Decimal("1.00")))


def test_daily_plan_is_full_compares_total_with_budget() -> None:
    plan = _plan()
    budget = Duration(Decimal("4.00"))

    assert plan.is_full(budget) is False

    plan.add_task(TaskId(uuid4()), Duration(Decimal("3.50")))
    assert plan.is_full(budget) is False

    plan.add_task(TaskId(uuid4()), Duration(Decimal("0.50")))
    assert plan.is_full(budget) is True

    with pytest.raises(DailyPlanFull):
        plan.add_task(TaskId(uuid4()), Duration(Decimal("0.25")), max_hours=budget)
    assert len(plan.task_ids) == 2

    with pytest.raises(TypeError):
        plan.is_full(Decimal("8"))  # type: ignore[arg-type]


def test_daily_plan_add_task_validates_types() -> None:
    plan = _plan()

    with pytest.raises(TypeError, match="TaskId"):
        plan.add_task(uuid4(), Duration(Decimal("1.00")))  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Duration"):
        plan.add_task(TaskId(uuid4()), Decimal("1.00"))  # type: ignore[arg-type]


def test_daily_plan_llm_generation_flag() -> None:
    plan = _plan()

    plan.mark_as_llm_generated()

    assert plan.generated_by_llm is True


def test_daily_plan_identity_and_owner_are_kept() -> None:
    user_id = UserId(uuid4())
    plan_id = DailyPlanId(uuid4())
    plan = _plan(user_id=user_id)

    plan.id = plan_id

    assert plan.id == plan_id
    assert plan.user_id == user_id
