"""Task deletion use case."""

from apps.tasks.application.commands import DeleteTaskCommand
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.application.scope import require_task_for_owner
from apps.tasks.domain.value_objects import TaskId


class DeleteTask:
    """Delete a task only when it belongs to the requesting user."""

    def __init__(self, tasks: TaskRepository) -> None:
        self._tasks = tasks

    def execute(self, command: DeleteTaskCommand) -> None:
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        self._tasks.delete(task)
