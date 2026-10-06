"""Goal creation use case."""

from apps.tasks.application.commands import CreateGoalCommand
from apps.tasks.application.dto import GoalDetails, goal_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository
from apps.tasks.domain.entities import Goal
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import UserId
from shared.domain.ports.clock import Clock


class CreateGoal:
    """Create and persist a goal for an authenticated user."""

    def __init__(self, goals: GoalRepository, clock: Clock) -> None:
        self._goals = goals
        self._clock = clock

    def execute(self, command: CreateGoalCommand) -> GoalDetails:
        try:
            goal = Goal.create(
                user_id=UserId(command.user_id),
                name=command.name,
                description=command.description,
                due_date=command.due_date,
                now=self._clock.now(),
            )
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error
        return goal_details(self._goals.save(goal))
