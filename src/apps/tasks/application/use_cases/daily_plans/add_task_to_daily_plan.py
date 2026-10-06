"""Daily plan scheduling use case."""

from apps.tasks.application.commands import AddTaskToDailyPlanCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import (
    DailyPlanDetails,
    daily_plan_details,
    ordered_tasks,
)
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.ports.repositories import (
    DailyPlanRepository,
    TaskRepository,
)
from apps.tasks.application.scope import (
    require_daily_plan_for_owner,
    require_task_for_owner,
)
from apps.tasks.domain.value_objects import DailyPlanId, TaskId


class AddTaskToDailyPlan:
    """Schedule a task on a day that still has room for it.

    ``DailyPlanFull`` and ``TaskAlreadyInPlan`` travel untouched: they are
    planning outcomes the interface reports as conflicts, not as bad input.
    """

    def __init__(
        self,
        plans: DailyPlanRepository,
        tasks: TaskRepository,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._plans = plans
        self._tasks = tasks
        self._policy = policy

    def execute(self, command: AddTaskToDailyPlanCommand) -> DailyPlanDetails:
        plan = require_daily_plan_for_owner(
            self._plans, DailyPlanId(command.plan_id), command.user_id
        )
        task = require_task_for_owner(
            self._tasks, TaskId(command.task_id), command.user_id
        )
        if task.id is None:
            raise InvalidTasksInput("A persisted task must have an identity.")
        plan.add_task(
            task.id,
            task.estimated_hours,
            max_hours=self._policy.daily_plan_max_hours,
        )
        updated = self._plans.update(plan)
        return daily_plan_details(
            updated,
            ordered_tasks(updated, self._tasks.get_by_ids(updated.task_ids)),
            self._policy.overwhelmed_threshold,
            self._policy.daily_plan_max_hours,
        )
