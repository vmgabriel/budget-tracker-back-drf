"""Task reopening use case."""

from apps.tasks.application.commands import ReopenTaskCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.application.scope import require_task_for_owner
from apps.tasks.domain.value_objects import TaskId
from shared.domain.ports.clock import Clock


class ReopenTask:
    """Send a completed task owned by the requesting user back to ``todo``.

    ``TaskNotCompleted`` is intentionally not translated, for the same reason
    ``MarkTaskAsDoing`` does not translate ``TaskAlreadyDone``: a task that was
    never completed cannot be reopened, and that is a business outcome rather
    than malformed input. ``TaskNotFound`` *is* raised by the scope helper, so a
    task belonging to somebody else stays indistinguishable from a missing one.
    """

    def __init__(
        self,
        tasks: TaskRepository,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._clock = clock
        self._policy = policy

    def execute(self, command: ReopenTaskCommand) -> TaskDetails:
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        task.reopen(now=self._clock.now())
        updated = self._tasks.update(task)
        return task_details(updated, self._policy.overwhelmed_threshold)
