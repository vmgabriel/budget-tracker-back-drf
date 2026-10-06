"""Goal listing use case."""

from apps.tasks.application.commands import ListUserGoalsCommand
from apps.tasks.application.dto import GoalDetails, goal_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository, TaskRepository
from apps.tasks.domain.value_objects import UserId


class ListUserGoals:
    """Return every goal of the requesting user with its task count."""

    def __init__(self, goals: GoalRepository, tasks: TaskRepository) -> None:
        self._goals = goals
        self._tasks = tasks

    def execute(self, command: ListUserGoalsCommand) -> list[GoalDetails]:
        goals = self._goals.get_by_user_id(UserId(command.user_id))
        details: list[GoalDetails] = []
        for goal in goals:
            if goal.id is None:
                raise InvalidTasksInput("A persisted goal must have an identity.")
            details.append(goal_details(goal, len(self._tasks.get_by_goal_id(goal.id))))
        return details
