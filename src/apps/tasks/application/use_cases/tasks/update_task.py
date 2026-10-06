"""Task update use case."""

from apps.tasks.application.commands import (
    UNSET,
    UpdateTaskCommand,
    resolve_optional_date,
)
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.application.scope import require_task_for_owner
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import Duration, Priority, TaskId
from shared.domain.ports.clock import Clock


class UpdateTask:
    """Apply partial changes to a task owned by the requesting user.

    The aggregate resets ``is_checked_by_llm`` when the name, description, or
    due date changed, so a task edited after evaluation is re-checked later.
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

    def execute(self, command: UpdateTaskCommand) -> TaskDetails:
        if (
            command.name is None
            and command.description is None
            and command.importance is None
            and command.estimated_hours is None
            and command.due_date is UNSET
        ):
            raise InvalidTasksInput("At least one task field is required.")

        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        due_date = resolve_optional_date(command.due_date, task.due_date)
        try:
            importance = (
                Priority(command.importance)
                if command.importance is not None
                else task.importance
            )
            estimated_hours = (
                Duration(command.estimated_hours)
                if command.estimated_hours is not None
                else task.estimated_hours
            )
            task.update(
                name=command.name if command.name is not None else task.name,
                description=(
                    command.description
                    if command.description is not None
                    else task.description
                ),
                importance=importance,
                estimated_hours=estimated_hours,
                due_date=due_date,
                now=self._clock.now(),
            )
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error
        updated = self._tasks.update(task)
        return task_details(updated, self._policy.overwhelmed_threshold)
