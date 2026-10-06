"""Tasks value-object tests."""

from dataclasses import FrozenInstanceError
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.tasks.domain.exceptions import InvalidDuration, InvalidThreshold
from apps.tasks.domain.value_objects import (
    GOAL_STATUS_CHOICES,
    PRIORITY_CHOICES,
    TASK_STATUS_CHOICES,
    DailyPlanId,
    Duration,
    GoalId,
    GoalStatus,
    OverwhelmedThreshold,
    Priority,
    TaskId,
    TaskStatus,
    UserId,
    normalize_date,
    normalize_description,
    normalize_text,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value_object", [TaskId, GoalId, DailyPlanId, UserId])
def test_identity_value_objects_wrap_uuids(
    value_object: type[TaskId | GoalId | DailyPlanId | UserId],
) -> None:
    identifier = uuid4()

    instance = value_object(identifier)

    assert instance.value == identifier
    assert str(instance) == str(identifier)
    with pytest.raises(FrozenInstanceError):
        instance.value = uuid4()  # type: ignore[misc]


def test_identity_value_objects_reject_non_uuids() -> None:
    with pytest.raises(TypeError):
        TaskId("not-a-uuid")  # type: ignore[arg-type]


def test_enums_expose_values_labels_and_choices() -> None:
    assert [priority.value for priority in Priority] == ["low", "medium", "high"]
    assert Priority.MEDIUM.label == "Medium"
    assert [status.value for status in TaskStatus] == ["todo", "doing", "done"]
    assert [status.value for status in GoalStatus] == [
        "active",
        "completed",
        "archived",
    ]
    assert PRIORITY_CHOICES == (("low", "Low"), ("medium", "Medium"), ("high", "High"))
    assert TASK_STATUS_CHOICES == (
        ("todo", "Todo"),
        ("doing", "Doing"),
        ("done", "Done"),
    )
    assert GOAL_STATUS_CHOICES == (
        ("active", "Active"),
        ("completed", "Completed"),
        ("archived", "Archived"),
    )


@pytest.mark.parametrize(
    ("priority", "expected"),
    [
        (Priority.LOW, Priority.MEDIUM),
        (Priority.MEDIUM, Priority.HIGH),
        (Priority.HIGH, Priority.HIGH),
    ],
)
def test_priority_promotes_one_level_and_saturates(
    priority: Priority, expected: Priority
) -> None:
    assert priority.promote() is expected


def test_duration_accepts_zero_and_two_decimals() -> None:
    assert Duration(Decimal("0")).hours == Decimal("0")
    assert Duration(Decimal("2.50")).hours == Decimal("2.50")
    assert Duration("1.5").hours == Decimal("1.5")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [Decimal("-0.01"), Decimal("1.999"), Decimal("1000000.00"), Decimal("NaN"), "abc"],
)
def test_duration_rejects_invalid_measurements(value: object) -> None:
    with pytest.raises(InvalidDuration):
        Duration(value)  # type: ignore[arg-type]


def test_duration_arithmetic_and_comparison() -> None:
    assert (Duration(Decimal("2.00")) + Duration(Decimal("1.25"))).hours == Decimal(
        "3.25"
    )
    assert (Duration(Decimal("2.00")) - Duration(Decimal("5.00"))).hours == Decimal("0")
    assert Duration(Decimal("4.00")).is_greater_than(Duration(Decimal("3.99")))
    assert not Duration(Decimal("4.00")).is_greater_than(Duration(Decimal("4.00")))


def test_overwhelmed_threshold_validates_and_compares() -> None:
    threshold = OverwhelmedThreshold(Decimal("4.0"))

    assert threshold.hours == Decimal("4.0")
    assert threshold.is_exceeded_by(Duration(Decimal("4.01")))
    assert not threshold.is_exceeded_by(Duration(Decimal("4.00")))


@pytest.mark.parametrize(
    "value", [Decimal("-1"), Decimal("2.001"), Decimal("Infinity")]
)
def test_overwhelmed_threshold_rejects_invalid_values(value: Decimal) -> None:
    with pytest.raises(InvalidThreshold):
        OverwhelmedThreshold(value)


def test_normalize_text_trims_and_enforces_limits() -> None:
    assert normalize_text("  Buy milk  ", label="Name", limit=10) == "Buy milk"

    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_text("   ", label="Name", limit=10)
    with pytest.raises(ValueError, match="10 characters"):
        normalize_text("x" * 11, label="Name", limit=10)


def test_normalize_description_allows_emptiness_and_strips() -> None:
    assert normalize_description("  **bold**  ", limit=50) == "**bold**"
    assert normalize_description(None, limit=50) == ""
    assert normalize_description("", limit=50) == ""

    with pytest.raises(ValueError, match="50 characters"):
        normalize_description("x" * 51, limit=50)


def test_normalize_date_accepts_only_calendar_dates() -> None:
    assert normalize_date(date(2026, 3, 1), label="Due date") == date(2026, 3, 1)
    assert normalize_date(None, label="Due date") is None

    with pytest.raises(ValueError, match="must be a date"):
        normalize_date(datetime(2026, 3, 1, 9, tzinfo=UTC), label="Due date")
