"""Task listing use case."""

from apps.tasks.application.commands import ListUserTasksCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.domain.value_objects import GoalId, TaskStatus, UserId


class ListUserTasks:
    """Return the tasks of one user, optionally narrowed by filters.

    Filtering happens in memory: the product serves a single owner whose task
    list is small, and keeping it here avoids a combinatorial port surface.
    """

    def __init__(
        self,
        tasks: TaskRepository,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._policy = policy

    def execute(self, command: ListUserTasksCommand) -> list[TaskDetails]:
        status = None
        if command.status is not None:
            try:
                status = TaskStatus(command.status)
            except ValueError as error:
                raise InvalidTasksInput("Unknown task status.") from error

        goal_id = GoalId(command.goal_id) if command.goal_id else None
        try:
            stored = self._tasks.get_by_user_id(UserId(command.user_id))
        except TypeError as error:
            raise InvalidTasksInput(str(error)) from error

        selected = [
            task
            for task in stored
            if (status is None or task.status is status)
            and (goal_id is None or task.goal_id == goal_id)
        ]
        threshold = self._policy.overwhelmed_threshold
        return [task_details(task, threshold) for task in selected]
