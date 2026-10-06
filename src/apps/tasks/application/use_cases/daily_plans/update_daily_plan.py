"""Daily plan update use case."""

from apps.tasks.application.commands import UNSET, UpdateDailyPlanCommand
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
from apps.tasks.application.scope import require_daily_plan_for_owner
from apps.tasks.domain.value_objects import DailyPlanId


class UpdateDailyPlan:
    """Record how a day came to be planned.

    Only the provenance flag is editable: the scheduled tasks change through the
    add/remove use cases, so a partial update can never contradict the hours a
    day actually holds.
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

    def execute(self, command: UpdateDailyPlanCommand) -> DailyPlanDetails:
        if command.generated_by_llm is UNSET:
            raise InvalidTasksInput("At least one daily plan field is required.")

        plan = require_daily_plan_for_owner(
            self._plans, DailyPlanId(command.plan_id), command.user_id
        )
        if command.generated_by_llm:
            plan.mark_as_llm_generated()
        else:
            plan.mark_as_manually_planned()
        updated = self._plans.update(plan)
        return daily_plan_details(
            updated,
            ordered_tasks(updated, self._tasks.get_by_ids(updated.task_ids)),
            self._policy.overwhelmed_threshold,
            self._policy.daily_plan_max_hours,
        )
