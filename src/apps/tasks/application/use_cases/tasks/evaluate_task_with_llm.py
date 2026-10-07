"""Task evaluation use case backed by the assistant port.

This is where a task actually changes because of the assistant. The task is
fetched inside the use case rather than by the caller, so ownership is checked
by the same :func:`require_task_for_owner` every other use case uses: the
assistant always acts as the task's own owner, never as an arbitrary
``user_id`` supplied from a message body.

Every assistant failure - unreachable, unparseable, or nonsensical - is
recorded on the task as ``llm_evaluation_failed`` and reported through the
outcome. The task's other fields are deliberately left alone: a broken
assistant must not be able to erase the effort estimate the owner entered.
"""

from dataclasses import dataclass
from uuid import UUID

from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.llm import TaskEvaluation
from apps.tasks.application.ports.llm import LlmAssistant
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.domain.entities import Task
from apps.tasks.domain.value_objects import TaskId
from shared.domain.ports.clock import Clock

EVALUATION_APPLIED = "applied"
EVALUATION_ALREADY_CHECKED = "already_checked"
EVALUATION_FAILED = "failed"
EVALUATION_NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class TaskEvaluationOutcome:
    """What happened when a task was sent to the assistant.

    ``status`` is a machine-readable verdict rather than a boolean, because the
    caller must distinguish "nothing to do" from "tried and failed": the first
    needs no follow-up, the second is worth retrying or surfacing to the owner.
    """

    status: str
    task: TaskDetails | None = None
    evaluation: TaskEvaluation | None = None

    @property
    def is_failure(self) -> bool:
        """Return whether the assistant could not be used."""
        return self.status == EVALUATION_FAILED


class EvaluateTaskWithLlm:
    """Assess a task's importance and effort, degrading to a recorded failure."""

    def __init__(
        self,
        tasks: TaskRepository,
        assistant: LlmAssistant,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._assistant = assistant
        self._clock = clock
        self._policy = policy

    def execute(self, task_id: UUID, *, force: bool = False) -> TaskEvaluationOutcome:
        """Evaluate the task identified by ``task_id`` unless it is up to date.

        ``force`` re-evaluates an already checked task. The owner-facing trigger
        passes it: asking for an evaluation again is an explicit request, and
        silently doing nothing would look like a broken button.
        """
        task = self._tasks.get_by_id(TaskId(task_id))
        if task is None:
            return TaskEvaluationOutcome(status=EVALUATION_NOT_FOUND)
        if task.is_checked_by_llm and not force:
            return TaskEvaluationOutcome(
                status=EVALUATION_ALREADY_CHECKED,
                task=self._details(task),
            )

        try:
            evaluation = self._assistant.evaluate_task(
                name=task.name,
                description=task.description,
                due_date_iso=task.due_date.isoformat() if task.due_date else None,
            )
        except Exception:
            # The assistant is external, so *any* failure degrades to a recorded
            # flag rather than escaping. A provider raising outside the port's
            # vocabulary must not crash the worker and leave the task stale.
            return self._record_failure(task)

        task.apply_llm_evaluation(
            evaluation.importance,
            evaluation.estimated_hours,
            now=self._clock.now(),
        )
        saved = self._tasks.update(task)
        return TaskEvaluationOutcome(
            status=EVALUATION_APPLIED,
            task=self._details(saved),
            evaluation=evaluation,
        )

    def _record_failure(self, task: Task) -> TaskEvaluationOutcome:
        """Flag the task as unevaluated, leaving its other fields untouched."""
        task.flag_llm_evaluation_failed()
        saved = self._tasks.update(task)
        return TaskEvaluationOutcome(
            status=EVALUATION_FAILED, task=self._details(saved)
        )

    def _details(self, task: Task) -> TaskDetails:
        return task_details(task, self._policy.overwhelmed_threshold)


__all__ = (
    "EVALUATION_ALREADY_CHECKED",
    "EVALUATION_APPLIED",
    "EVALUATION_FAILED",
    "EVALUATION_NOT_FOUND",
    "EvaluateTaskWithLlm",
    "TaskEvaluationOutcome",
)
