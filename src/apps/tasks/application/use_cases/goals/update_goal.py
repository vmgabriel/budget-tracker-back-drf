"""Goal update use case."""

from apps.tasks.application.commands import (
    UNSET,
    UpdateGoalCommand,
    resolve_optional_date,
)
from apps.tasks.application.dto import GoalDetails, goal_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository, TaskRepository
from apps.tasks.application.scope import require_goal_for_owner
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import GoalId
from shared.domain.ports.clock import Clock


class UpdateGoal:
    """Apply partial changes to a goal owned by the requesting user."""

    def __init__(
        self,
        goals: GoalRepository,
        tasks: TaskRepository,
        clock: Clock,
    ) -> None:
        self._goals = goals
        self._tasks = tasks
        self._clock = clock

    def execute(self, command: UpdateGoalCommand) -> GoalDetails:
        if (
            command.name is None
            and command.description is None
            and command.due_date is UNSET
        ):
            raise InvalidTasksInput("At least one goal field is required.")

        goal = require_goal_for_owner(
            self._goals, GoalId(command.goal_id), command.user_id
        )
        if goal.id is None:
            raise InvalidTasksInput("A persisted goal must have an identity.")
        due_date = resolve_optional_date(command.due_date, goal.due_date)
        try:
            goal.update(
                name=command.name if command.name is not None else goal.name,
                description=(
                    command.description
                    if command.description is not None
                    else goal.description
                ),
                due_date=due_date,
                now=self._clock.now(),
            )
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error
        updated = self._goals.update(goal)
        if updated.id is None:
            raise InvalidTasksInput("A persisted goal must have an identity.")
        return goal_details(updated, len(self._tasks.get_by_goal_id(updated.id)))
