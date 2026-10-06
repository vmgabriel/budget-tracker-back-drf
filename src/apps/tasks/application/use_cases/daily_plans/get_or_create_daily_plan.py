"""Daily plan creation-on-demand use case."""

from apps.tasks.application.commands import GetOrCreateDailyPlanCommand
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
from apps.tasks.domain.entities import DailyPlan
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import UserId, normalize_date
from shared.domain.ports.clock import Clock


class GetOrCreateDailyPlan:
    """Open the plan of one day, creating an empty one when it does not exist.

    Opening a day should never fail just because it was never planned, so the
    missing case is materialised here instead of returning a 404.
    """

    def __init__(
        self,
        plans: DailyPlanRepository,
        tasks: TaskRepository,
        clock: Clock,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._plans = plans
        self._tasks = tasks
        self._clock = clock
        self._policy = policy

    def execute(self, command: GetOrCreateDailyPlanCommand) -> DailyPlanDetails:
        try:
            user_id = UserId(command.user_id)
            day = normalize_date(command.date, label="Daily plan date")
            if day is None:
                raise ValueError("Daily plan date must be a date.")
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error

        plan = self._plans.get_by_user_and_date(user_id, day)
        if plan is None:
            created = DailyPlan.create(
                user_id=user_id,
                date=day,
                now=self._clock.now(),
            )
            plan = self._plans.save(created)
        return daily_plan_details(
            plan,
            ordered_tasks(plan, self._tasks.get_by_ids(plan.task_ids)),
            self._policy.overwhelmed_threshold,
            self._policy.daily_plan_max_hours,
        )
