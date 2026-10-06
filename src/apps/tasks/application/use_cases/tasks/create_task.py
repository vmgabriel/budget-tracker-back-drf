"""Task creation use case."""

from apps.tasks.application.commands import CreateTaskCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import TaskRepository
from apps.tasks.domain.entities import Task
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import (
    Duration,
    GoalId,
    Priority,
    UserId,
)
from shared.domain.ports.clock import Clock


class CreateTask:
    """Create and persist a task for an authenticated user."""

    def __init__(
        self,
        tasks: TaskRepository,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._clock = clock
        self._policy = policy

    def execute(self, command: CreateTaskCommand) -> TaskDetails:
        try:
            task = Task.create(
                user_id=UserId(command.user_id),
                name=command.name,
                description=command.description,
                importance=Priority(command.importance),
                estimated_hours=Duration(command.estimated_hours),
                due_date=command.due_date,
                goal_id=GoalId(command.goal_id) if command.goal_id else None,
                now=self._clock.now(),
            )
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error
        saved = self._tasks.save(task)
        return task_details(saved, self._policy.overwhelmed_threshold)
