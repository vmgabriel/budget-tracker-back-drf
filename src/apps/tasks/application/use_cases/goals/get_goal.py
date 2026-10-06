"""Single goal query use case."""

from apps.tasks.application.commands import GetGoalCommand
from apps.tasks.application.dto import GoalDetails, goal_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository, TaskRepository
from apps.tasks.application.scope import require_goal_for_owner
from apps.tasks.domain.value_objects import GoalId


class GetGoal:
    """Return a goal only when it belongs to the requesting user."""

    def __init__(self, goals: GoalRepository, tasks: TaskRepository) -> None:
        self._goals = goals
        self._tasks = tasks

    def execute(self, command: GetGoalCommand) -> GoalDetails:
        goal = require_goal_for_owner(
            self._goals, GoalId(command.goal_id), command.user_id
        )
        if goal.id is None:
            raise InvalidTasksInput("A persisted goal must have an identity.")
        return goal_details(goal, len(self._tasks.get_by_goal_id(goal.id)))
