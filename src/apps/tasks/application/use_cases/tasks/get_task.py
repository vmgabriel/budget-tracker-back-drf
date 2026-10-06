"""Single task query use case."""

from apps.tasks.application.commands import GetTaskCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.application.scope import require_task_for_owner
from apps.tasks.domain.value_objects import TaskId


class GetTask:
    """Return a task only when it belongs to the requesting user."""

    def __init__(
        self,
        tasks: TaskRepository,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._policy = policy

    def execute(self, command: GetTaskCommand) -> TaskDetails:
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        return task_details(task, self._policy.overwhelmed_threshold)
