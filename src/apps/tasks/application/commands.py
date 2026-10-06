"""Inputs accepted by the tasks use cases.

Commands are frozen dataclasses of *primitives* (UUIDs, strings, decimals,
dates) so HTTP payloads never need to know about value objects, and use cases
stay responsible for building the domain objects they need.

Partial updates use the :data:`UNSET` sentinel instead of ``None`` because
``None`` is a meaningful value for ``due_date``: it clears the deadline. With
``None``-means-unchanged, a deadline could never be removed once set.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Unset:
    """Sentinel type marking a command field the caller did not send."""

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = Unset()


def resolve_optional_date(
    value: date | None | Unset, current: date | None
) -> date | None:
    """Return the stored date when the caller omitted the field.

    ``None`` clears a deadline, so "omitted" and "cleared" need distinct
    representations; this keeps that distinction in one place.
    """
    if isinstance(value, Unset):
        return current
    return value


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Input required to create a task."""

    user_id: UUID
    name: str
    description: str
    importance: str
    estimated_hours: Decimal
    due_date: date | None = None
    goal_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class GetTaskCommand:
    """Input required to read a single task."""

    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ListUserTasksCommand:
    """Input required to list the tasks of one user.

    ``status`` and ``goal_id`` are optional filters; ``None`` keeps every task.
    """

    user_id: UUID
    status: str | None = None
    goal_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class UpdateTaskCommand:
    """Partial input accepted when updating a task.

    Every field left as ``UNSET`` keeps its stored value.
    """

    task_id: UUID
    user_id: UUID
    name: str | None = None
    description: str | None = None
    importance: str | None = None
    estimated_hours: Decimal | None = None
    due_date: date | None | Unset = UNSET


@dataclass(frozen=True, slots=True)
class DeleteTaskCommand:
    """Input required to delete a task."""

    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class MarkTaskAsDoingCommand:
    """Input required to move a task to ``doing``."""

    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class MarkTaskAsDoneCommand:
    """Input required to complete a task."""

    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class PromoteTaskPriorityCommand:
    """Input required to raise the importance of a carried-over task."""

    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class CreateGoalCommand:
    """Input required to create a goal."""

    user_id: UUID
    name: str
    description: str
    due_date: date | None = None


@dataclass(frozen=True, slots=True)
class GetGoalCommand:
    """Input required to read a single goal."""

    goal_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ListUserGoalsCommand:
    """Input required to list the goals of one user."""

    user_id: UUID


@dataclass(frozen=True, slots=True)
class UpdateGoalCommand:
    """Partial input accepted when updating a goal."""

    goal_id: UUID
    user_id: UUID
    name: str | None = None
    description: str | None = None
    due_date: date | None | Unset = UNSET


@dataclass(frozen=True, slots=True)
class DeleteGoalCommand:
    """Input required to delete a goal."""

    goal_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class LinkTaskToGoalCommand:
    """Input required to associate a task with a goal."""

    goal_id: UUID
    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class UnlinkTaskFromGoalCommand:
    """Input required to remove the goal association of a task."""

    goal_id: UUID
    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class GetOrCreateDailyPlanCommand:
    """Input required to open the plan of one day, creating it when missing."""

    user_id: UUID
    date: date


@dataclass(frozen=True, slots=True)
class GetDailyPlanCommand:
    """Input required to read a single daily plan."""

    plan_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class AddTaskToDailyPlanCommand:
    """Input required to schedule a task on a day."""

    plan_id: UUID
    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class RemoveTaskFromDailyPlanCommand:
    """Input required to unschedule a task from a day."""

    plan_id: UUID
    task_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class ListDailyPlansCommand:
    """Input required to list plans within an inclusive date range."""

    user_id: UUID
    start_date: date
    end_date: date
