"""Task decomposition use case backed by the assistant port.

An overwhelming task is replaced by a goal plus the subtasks that achieve it.
The original is marked ``done`` rather than deleted: the decomposition is an
assistant's suggestion applied to the owner's own data, and destroying the
source task would make a bad suggestion unrecoverable.

Atomicity is *not* handled here. Writing a goal, writing its subtasks, and
closing the original are a single decision, and a half-applied decomposition
leaves subtasks with no goal - worse than no change at all. The application
layer therefore requires the caller to wrap this use case in a transaction;
the Celery task does so, which keeps Django out of this module.
"""

from dataclasses import dataclass
from uuid import UUID

from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import (
    GoalDetails,
    TaskDetails,
    goal_details,
    task_details,
)
from apps.tasks.application.llm import TaskDecomposition
from apps.tasks.application.ports.llm import LlmAssistant
from apps.tasks.application.ports.repositories import (
    GoalRepository,
    TaskRepository,
)
from apps.tasks.domain.entities import Goal, Task
from apps.tasks.domain.value_objects import (
    GoalId,
    Priority,
    TaskId,
    TaskStatus,
)
from shared.domain.ports.clock import Clock

DECOMPOSITION_APPLIED = "applied"
DECOMPOSITION_NOT_OVERWHELMING = "not_overwhelming"
DECOMPOSITION_FAILED = "failed"
DECOMPOSITION_NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class TaskDecompositionOutcome:
    """What happened when a task was sent to the assistant to be broken up."""

    status: str
    goal: GoalDetails | None = None
    subtasks: tuple[TaskDetails, ...] = ()
    decomposition: TaskDecomposition | None = None

    @property
    def is_failure(self) -> bool:
        """Return whether the assistant could not be used."""
        return self.status == DECOMPOSITION_FAILED


class DecomposeOverwhelmingTask:
    """Turn one too-big task into a goal and the subtasks that reach it."""

    def __init__(
        self,
        tasks: TaskRepository,
        goals: GoalRepository,
        assistant: LlmAssistant,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._goals = goals
        self._assistant = assistant
        self._clock = clock
        self._policy = policy

    def execute(self, task_id: UUID) -> TaskDecompositionOutcome:
        """Decompose the task when its estimate is above the threshold.

        A task that already fits in a day is left alone: splitting it would
        produce more bookkeeping than progress, and the assistant was asked to
        expand only what is genuinely too big.
        """
        task = self._tasks.get_by_id(TaskId(task_id))
        if task is None:
            return TaskDecompositionOutcome(status=DECOMPOSITION_NOT_FOUND)
        if not task.is_overwhelmed(self._policy.overwhelmed_threshold):
            return TaskDecompositionOutcome(status=DECOMPOSITION_NOT_OVERWHELMING)

        try:
            decomposition = self._assistant.decompose_task(
                name=task.name,
                description=task.description,
            )
        except Exception:
            # As with evaluation, an assistant that fails in any way leaves the
            # task exactly as it was except for the recorded failure flag.
            return self._record_failure(task)

        goal = self._save_goal(task, decomposition)
        subtasks = self._create_subtasks(task, decomposition, self._goal_id(goal))
        self._close(task)
        return TaskDecompositionOutcome(
            status=DECOMPOSITION_APPLIED,
            goal=goal_details(goal),
            subtasks=tuple(
                task_details(subtask, self._policy.overwhelmed_threshold)
                for subtask in subtasks
            ),
            decomposition=decomposition,
        )

    def _save_goal(self, task: Task, decomposition: TaskDecomposition) -> Goal:
        """Store the umbrella outcome, carrying over the original deadline."""
        goal = self._goals.save(
            Goal.create(
                user_id=task.user_id,
                name=decomposition.goal_name,
                description=task.description,
                due_date=task.due_date,
                now=self._clock.now(),
            )
        )
        return goal

    def _goal_id(self, goal: Goal) -> GoalId:
        """Return the stored goal's identity, which persistence must provide."""
        if goal.id is None:
            raise ValueError("A persisted goal must have an identity.")
        return goal.id

    def _create_subtasks(
        self,
        task: Task,
        decomposition: TaskDecomposition,
        goal_id: GoalId,
    ) -> list[Task]:
        """Create each proposed subtask under the new goal.

        Subtasks inherit the parent's deadline, since the umbrella cannot be
        reached after it, and start at ``low`` importance: the assistant ranked
        the parent, not its steps, and pretending otherwise would let a guess
        silently promote work.
        """
        created: list[Task] = []
        for proposal in decomposition.subtasks:
            subtask = Task.create(
                user_id=task.user_id,
                name=proposal.name,
                description=proposal.description,
                importance=Priority.LOW,
                estimated_hours=proposal.estimated_hours,
                due_date=task.due_date,
                goal_id=goal_id,
                now=self._clock.now(),
            )
            created.append(self._tasks.save(subtask))
        return created

    def _close(self, task: Task) -> None:
        """Mark the decomposed task as done instead of deleting it."""
        if task.status is not TaskStatus.DONE:
            task.mark_as_done(now=self._clock.now())
        self._tasks.update(task)

    def _record_failure(self, task: Task) -> TaskDecompositionOutcome:
        """Flag the task as unevaluated, leaving its other fields untouched."""
        task.flag_llm_evaluation_failed()
        self._tasks.update(task)
        return TaskDecompositionOutcome(status=DECOMPOSITION_FAILED)


__all__ = (
    "DECOMPOSITION_APPLIED",
    "DECOMPOSITION_FAILED",
    "DECOMPOSITION_NOT_FOUND",
    "DECOMPOSITION_NOT_OVERWHELMING",
    "DecomposeOverwhelmingTask",
    "TaskDecompositionOutcome",
)
