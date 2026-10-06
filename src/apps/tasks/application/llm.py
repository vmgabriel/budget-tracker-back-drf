"""Typed contracts for assistant (LLM) assistance.

The assistant is an *external* collaborator: it can be unreachable, and when it
answers it may answer with anything at all. This module therefore owns two
things and nothing else:

* the small set of failure vocabulary callers must handle
  (:class:`LlmUnavailableError`, :class:`LlmInvalidResponseError`), and
* frozen dataclasses plus strict parsers that turn a raw JSON payload into
  validated data, reusing the domain value objects as the last line of defence.

It is pure Python so the rules can be tested without infrastructure. No prompt
text lives here: prompts are an infrastructure concern, because they describe
how a particular model must be spoken to.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.tasks.domain.value_objects import Duration, Priority, TaskId


class LlmError(Exception):
    """Base class for assistant failures.

    Every failure mode is recoverable in the product sense: the caller records
    it (``llm_evaluation_failed``) and falls back to safe defaults, so no
    subclass is ever allowed to escape as a task crash.
    """


class LlmUnavailableError(LlmError):
    """Raised when the assistant cannot be reached or refuses the request."""


class LlmInvalidResponseError(LlmError):
    """Raised when the assistant answers with unusable JSON."""


@dataclass(frozen=True, slots=True)
class TaskEvaluation:
    """A validated assessment of one task."""

    importance: Priority
    estimated_hours: Duration
    suggested_goal: str | None = None


@dataclass(frozen=True, slots=True)
class SubtaskProposal:
    """One step proposed as part of a decomposed task."""

    name: str
    description: str
    estimated_hours: Duration


@dataclass(frozen=True, slots=True)
class TaskDecomposition:
    """A validated proposal to break an overwhelming task into smaller ones."""

    goal_name: str
    subtasks: tuple[SubtaskProposal, ...]


@dataclass(frozen=True, slots=True)
class DailyPlanProposal:
    """A validated proposal for how to fill one day.

    ``total_hours`` is what the assistant *claims* it scheduled; the sum of the
    selected tasks' real estimates is recomputed by the caller from storage, so
    a mismatch never silently writes wrong hours into the plan.
    """

    task_ids: tuple[TaskId, ...]
    total_hours: Duration


def parse_task_evaluation(payload: Mapping[str, Any]) -> TaskEvaluation:
    """Return the validated evaluation contained in ``payload``.

    Raises :class:`LlmInvalidResponseError` when a required field is missing,
    mistyped, or outside the domain's own bounds.
    """
    mapping = _require_mapping(payload, "task evaluation")
    importance = _require_priority(mapping.get("importance"), "importance")
    estimated_hours = _require_duration(
        mapping.get("estimated_hours"),
        "estimated_hours",
    )
    suggested_goal = _optional_text(mapping.get("suggested_goal"), "suggested_goal")
    return TaskEvaluation(
        importance=importance,
        estimated_hours=estimated_hours,
        suggested_goal=suggested_goal,
    )


def parse_task_decomposition(payload: Mapping[str, Any]) -> TaskDecomposition:
    """Return the validated decomposition contained in ``payload``."""
    mapping = _require_mapping(payload, "task decomposition")
    goal_name = _require_text(mapping.get("goal_name"), "goal_name")
    raw_subtasks = mapping.get("subtasks")
    if not isinstance(raw_subtasks, Sequence) or isinstance(raw_subtasks, (str, bytes)):
        raise LlmInvalidResponseError("Decomposition 'subtasks' must be a list.")
    if not raw_subtasks:
        raise LlmInvalidResponseError("Decomposition 'subtasks' cannot be empty.")
    subtasks = tuple(
        _parse_subtask(item, index) for index, item in enumerate(raw_subtasks)
    )
    return TaskDecomposition(goal_name=goal_name, subtasks=subtasks)


def parse_daily_plan_proposal(
    payload: Mapping[str, Any],
    allowed_task_ids: Iterable[TaskId],
) -> DailyPlanProposal:
    """Return the validated day proposal, clipped to tasks that actually exist.

    ``allowed_task_ids`` is the caller's backlog. An identifier outside it is
    dropped rather than trusted: the assistant may hallucinate, and a schedule
    must never reference a task the user does not own.
    """
    mapping = _require_mapping(payload, "daily plan proposal")
    raw_task_ids = mapping.get("task_ids")
    if not isinstance(raw_task_ids, Sequence) or isinstance(raw_task_ids, (str, bytes)):
        raise LlmInvalidResponseError("Plan proposal 'task_ids' must be a list.")
    allowed = set(allowed_task_ids)
    selected: list[TaskId] = []
    for raw_value in raw_task_ids:
        if not isinstance(raw_value, str):
            raise LlmInvalidResponseError("Plan proposal 'task_ids' must be strings.")
        try:
            candidate = TaskId(UUID(raw_value))
        except (TypeError, ValueError) as error:
            raise LlmInvalidResponseError(
                f"Plan proposal contains an invalid task id: {raw_value!r}."
            ) from error
        if candidate in allowed and candidate not in selected:
            selected.append(candidate)
    total_hours = _require_duration(mapping.get("total_hours"), "total_hours")
    return DailyPlanProposal(task_ids=tuple(selected), total_hours=total_hours)


def _parse_subtask(item: Any, index: int) -> SubtaskProposal:
    mapping = _require_mapping(item, f"subtask at position {index}")
    return SubtaskProposal(
        name=_require_text(mapping.get("name"), f"subtasks[{index}].name"),
        description=_optional_text(
            mapping.get("description"),
            f"subtasks[{index}].description",
        )
        or "",
        estimated_hours=_require_duration(
            mapping.get("estimated_hours"),
            f"subtasks[{index}].estimated_hours",
        ),
    )


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise LlmInvalidResponseError(f"Expected a JSON object for {label}.")
    return value


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LlmInvalidResponseError(f"Field '{label}' must be a non-empty string.")
    return value.strip()


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LlmInvalidResponseError(f"Field '{label}' must be a string or null.")
    return value.strip() or None


def _require_priority(value: Any, label: str) -> Priority:
    if isinstance(value, Priority):
        return value
    if not isinstance(value, str):
        raise LlmInvalidResponseError(
            f"Field '{label}' must be one of high, medium or low."
        )
    try:
        return Priority(value.strip().lower())
    except ValueError as error:
        raise LlmInvalidResponseError(
            f"Field '{label}' must be one of high, medium or low."
        ) from error


def _require_duration(value: Any, label: str) -> Duration:
    """Coerce ``value`` into a ``Duration``, reporting failures as LLM errors."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise LlmInvalidResponseError(f"Field '{label}' must be a number of hours.")
    try:
        return Duration(Decimal(str(value)))
    except Exception as error:  # domain bounds (negative, too long, too precise)
        raise LlmInvalidResponseError(
            f"Field '{label}' is not a valid number of hours: {error}."
        ) from error
