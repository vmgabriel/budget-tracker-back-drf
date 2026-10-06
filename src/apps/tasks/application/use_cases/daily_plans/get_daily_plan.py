"""Daily plan retrieval use case."""

from apps.tasks.application.commands import GetDailyPlanCommand
from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.dto import (
    DailyPlanDetails,
    daily_plan_details,
    ordered_tasks,
)
from apps.tasks.application.ports.repositories import (
    DailyPlanRepository,
    TaskRepository,
)
from apps.tasks.application.scope import require_daily_plan_for_owner
from apps.tasks.domain.value_objects import DailyPlanId


class GetDailyPlan:
    """Return a stored daily plan only when it belongs to the requesting user."""

    def __init__(
        self,
        plans: DailyPlanRepository,
        tasks: TaskRepository,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._plans = plans
        self._tasks = tasks
        self._policy = policy

    def execute(self, command: GetDailyPlanCommand) -> DailyPlanDetails:
        plan = require_daily_plan_for_owner(
            self._plans, DailyPlanId(command.plan_id), command.user_id
        )
        return daily_plan_details(
            plan,
            ordered_tasks(plan, self._tasks.get_by_ids(plan.task_ids)),
            self._policy.overwhelmed_threshold,
            self._policy.daily_plan_max_hours,
        )
