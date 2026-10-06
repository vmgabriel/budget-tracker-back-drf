"""Port describing the assistant the tasks context depends on.

The use cases speak this protocol, never ``httpx`` and never Ollama: swapping
the local model for a hosted provider must not touch a single use case.
"""

from typing import Protocol

from apps.tasks.application.llm import (
    DailyPlanProposal,
    LlmUnavailableError,
    TaskDecomposition,
    TaskEvaluation,
)
from apps.tasks.domain.value_objects import TaskId


class LlmAssistant(Protocol):
    """A text assistant reachable over the network."""

    def evaluate_task(
        self,
        *,
        name: str,
        description: str,
        due_date_iso: str | None,
    ) -> TaskEvaluation:
        """Assess importance and effort for a single task.

        Raises :class:`LlmUnavailableError` or
        :class:`LlmInvalidResponseError`; never a parsing or transport detail.
        """
        ...

    def decompose_task(
        self,
        *,
        name: str,
        description: str,
    ) -> TaskDecomposition:
        """Break an overwhelming task into a goal and smaller subtasks."""
        ...

    def plan_day(
        self,
        *,
        date_iso: str,
        max_hours: str,
        candidates: tuple[tuple[TaskId, str, str, str, str | None], ...],
    ) -> DailyPlanProposal:
        """Choose which backlog tasks fill one day within ``max_hours``.

        ``candidates`` is one tuple per candidate task:
        ``(task_id, name, importance, estimated_hours, due_date_iso)``.
        """
        ...

    def is_available(self) -> bool:
        """Return whether the assistant can be reached right now."""
        ...


__all__ = (
    "DailyPlanProposal",
    "LlmAssistant",
    "LlmUnavailableError",
    "TaskDecomposition",
    "TaskEvaluation",
)
