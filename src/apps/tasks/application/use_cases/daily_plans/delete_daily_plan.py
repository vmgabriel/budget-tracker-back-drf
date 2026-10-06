"""Daily plan deletion use case."""

from apps.tasks.application.commands import DeleteDailyPlanCommand
from apps.tasks.application.ports.repositories import DailyPlanRepository
from apps.tasks.application.scope import require_daily_plan_for_owner
from apps.tasks.domain.value_objects import DailyPlanId


class DeleteDailyPlan:
    """Discard a day without touching the tasks it referenced."""

    def __init__(self, plans: DailyPlanRepository) -> None:
        self._plans = plans

    def execute(self, command: DeleteDailyPlanCommand) -> None:
        plan = require_daily_plan_for_owner(
            self._plans, DailyPlanId(command.plan_id), command.user_id
        )
        self._plans.delete(plan)
