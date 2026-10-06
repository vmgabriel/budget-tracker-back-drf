"""Goal deletion use case."""

from apps.tasks.application.commands import DeleteGoalCommand
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository, TaskRepository
from apps.tasks.application.scope import require_goal_for_owner
from apps.tasks.domain.value_objects import GoalId
from shared.domain.ports.clock import Clock


class DeleteGoal:
    """Delete a goal, keeping its tasks and detaching them from it.

    Losing a goal must never lose work: the tasks that pointed at it are
    unlinked and survive as standalone tasks.
    """

    def __init__(
        self,
        goals: GoalRepository,
        tasks: TaskRepository,
        clock: Clock,
    ) -> None:
        self._goals = goals
        self._tasks = tasks
        self._clock = clock

    def execute(self, command: DeleteGoalCommand) -> None:
        goal = require_goal_for_owner(
            self._goals, GoalId(command.goal_id), command.user_id
        )
        if goal.id is None:
            raise InvalidTasksInput("A persisted goal must have an identity.")
        now = self._clock.now()
        for task in self._tasks.get_by_goal_id(goal.id):
            task.unlink_from_goal(now=now)
            self._tasks.update(task)
        self._goals.delete(goal)
