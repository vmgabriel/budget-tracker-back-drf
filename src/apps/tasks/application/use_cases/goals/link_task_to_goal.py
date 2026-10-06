"""Task-to-goal association use case."""

from apps.tasks.application.commands import LinkTaskToGoalCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import TaskDetails, task_details
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import GoalRepository, TaskRepository
from apps.tasks.application.scope import require_goal_for_owner, require_task_for_owner
from apps.tasks.domain.value_objects import GoalId, TaskId
from shared.domain.ports.clock import Clock


class LinkTaskToGoal:
    """Associate a task with a goal, both owned by the requesting user.

    Both sides are owner-checked: linking to somebody else's goal would leak
    the grouping structure of that user.
    """

    def __init__(
        self,
        tasks: TaskRepository,
        goals: GoalRepository,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._tasks = tasks
        self._goals = goals
        self._clock = clock
        self._policy = policy

    def execute(self, command: LinkTaskToGoalCommand) -> TaskDetails:
        require_goal_for_owner(self._goals, GoalId(command.goal_id), command.user_id)
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        if task.goal_id == GoalId(command.goal_id):
            raise InvalidTasksInput("Task is already linked to this goal.")
        task.link_to_goal(GoalId(command.goal_id), now=self._clock.now())
        updated = self._tasks.update(task)
        return task_details(updated, self._policy.overwhelmed_threshold)
