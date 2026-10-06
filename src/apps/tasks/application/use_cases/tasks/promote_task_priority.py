"""Task priority promotion use case."""

from apps.tasks.application.commands import PromoteTaskPriorityCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.application.scope import require_task_for_owner
from apps.tasks.domain.value_objects import TaskId
from shared.domain.ports.clock import Clock


class PromoteTaskPriority:
    """Raise the importance of a carried-over task by one level."""

    def __init__(
        self,
        tasks: TaskRepository,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._clock = clock
        self._policy = policy

    def execute(self, command: PromoteTaskPriorityCommand) -> TaskDetails:
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        task.promote_priority(now=self._clock.now())
        updated = self._tasks.update(task)
        return task_details(updated, self._policy.overwhelmed_threshold)
