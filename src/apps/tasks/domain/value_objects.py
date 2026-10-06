"""Immutable value objects for the tasks domain.

Pure Python only: no Django, DRF, Celery, or persistence imports are allowed
here, so the module stays testable without infrastructure.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from apps.tasks.domain.exceptions import (
    InvalidDuration,
    InvalidThreshold,
    TasksDomainError,
)

HOUR_STEP = Decimal("0.01")
MAX_HOURS = Decimal("999999.99")
MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000

CalendarDate = date
"""Alias for the calendar date type.

``DailyPlan`` has a field named ``date``, which shadows the imported type
inside the class body; annotating that field with this alias keeps the type
checker honest without renaming the public attribute.
"""


class Priority(StrEnum):
    """Importance assigned to a task; the order matters for promotion."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        """Return the human-readable priority label."""
        return self.value.capitalize()

    def promote(self) -> "Priority":
        """Return the next importance level, saturating at ``high``.

        Used when an unfinished task carries over to another day: what was
        deprioritised yesterday deserves more attention today.
        """
        order = PRIORITY_ORDER
        index = order.index(self)
        return order[min(index + 1, len(order) - 1)]


PRIORITY_ORDER: tuple[Priority, ...] = (
    Priority.LOW,
    Priority.MEDIUM,
    Priority.HIGH,
)

PRIORITY_CHOICES: tuple[tuple[str, str], ...] = (
    (Priority.LOW.value, "Low"),
    (Priority.MEDIUM.value, "Medium"),
    (Priority.HIGH.value, "High"),
)


class TaskStatus(StrEnum):
    """Lifecycle states of a single task."""

    TODO = "todo"
    DOING = "doing"
    DONE = "done"

    @property
    def label(self) -> str:
        """Return the human-readable status label."""
        return self.value.capitalize()


TASK_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    (TaskStatus.TODO.value, "Todo"),
    (TaskStatus.DOING.value, "Doing"),
    (TaskStatus.DONE.value, "Done"),
)


class GoalStatus(StrEnum):
    """Lifecycle states of a goal (macrotask)."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

    @property
    def label(self) -> str:
        """Return the human-readable status label."""
        return self.value.capitalize()


GOAL_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    (GoalStatus.ACTIVE.value, "Active"),
    (GoalStatus.COMPLETED.value, "Completed"),
    (GoalStatus.ARCHIVED.value, "Archived"),
)


def _require_uuid(value: UUID, label: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{label} must contain a UUID.")


def _to_hours(value: Decimal, error: type[TasksDomainError], label: str) -> Decimal:
    """Coerce ``value`` to a finite, non-negative decimal with two places."""
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as conversion_error:
        raise error(f"{label} must be a valid decimal value.") from conversion_error
    if not amount.is_finite():
        raise error(f"{label} must be finite.")
    if amount < 0:
        raise error(f"{label} cannot be negative.")
    if amount > MAX_HOURS:
        raise error(f"{label} must not exceed {MAX_HOURS}.")
    if amount != amount.quantize(HOUR_STEP):
        raise error(f"{label} must have at most two decimal places.")
    return amount


def normalize_text(value: str, *, label: str, limit: int) -> str:
    """Return a non-empty, length-bounded version of ``value``."""
    if not isinstance(value, str):
        raise TypeError(f"{label} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} cannot be empty.")
    if len(normalized) > limit:
        raise ValueError(f"{label} cannot exceed {limit} characters.")
    return normalized


def normalize_description(value: str | None, *, limit: int) -> str:
    """Return a markdown description, allowing an intentionally empty one.

    Descriptions are prose written by the owner, so surrounding whitespace is
    dropped but emptiness is legitimate: a task may be just a name.
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("Description must be a string.")
    trimmed = value.strip()
    if len(trimmed) > limit:
        raise ValueError(f"Description cannot exceed {limit} characters.")
    return trimmed


def normalize_date(value: date | None, *, label: str) -> date | None:
    """Return ``value`` when it is a plain calendar date, rejecting anything else.

    ``datetime`` instances are rejected on purpose: a deadline belongs to a
    day, and silently truncating a timestamp would hide that precision loss.
    """
    if value is None:
        return None
    if not isinstance(value, date) or isinstance(value, datetime):
        raise ValueError(f"{label} must be a date.")
    return value


@dataclass(frozen=True, slots=True)
class TaskId:
    """Identity of a persisted task."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "TaskId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class GoalId:
    """Identity of a persisted goal."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "GoalId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DailyPlanId:
    """Identity of a persisted daily plan."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "DailyPlanId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UserId:
    """Reference to a user owned by the users context.

    Duplicated intentionally: bounded contexts never import each other's
    models, so each context keeps its own copy of shared identity concepts.
    """

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "UserId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Duration:
    """A non-negative amount of hours, with at most two decimal places."""

    hours: Decimal

    def __post_init__(self) -> None:
        amount = _to_hours(self.hours, InvalidDuration, "Duration")
        object.__setattr__(self, "hours", amount)

    def __add__(self, other: "Duration") -> "Duration":
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(self.hours + other.hours)

    def __sub__(self, other: "Duration") -> "Duration":
        if not isinstance(other, Duration):
            return NotImplemented
        return Duration(max(self.hours - other.hours, Decimal("0")))

    def is_greater_than(self, other: "Duration") -> bool:
        """Return whether this duration exceeds ``other``."""
        if not isinstance(other, Duration):
            raise TypeError("Comparison requires a Duration.")
        return self.hours > other.hours


@dataclass(frozen=True, slots=True)
class OverwhelmedThreshold:
    """The hour estimate above which a task counts as overwhelming.

    This object only validates the value; the default that applies to a user
    is application policy and lives in ``apps.tasks.application.config``.
    """

    hours: Decimal

    def __post_init__(self) -> None:
        amount = _to_hours(self.hours, InvalidThreshold, "Overwhelmed threshold")
        object.__setattr__(self, "hours", amount)

    def is_exceeded_by(self, duration: Duration) -> bool:
        """Return whether ``duration`` surpasses this threshold."""
        if not isinstance(duration, Duration):
            raise TypeError("Comparison requires a Duration.")
        return duration.hours > self.hours
