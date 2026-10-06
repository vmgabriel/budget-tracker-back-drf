"""Daily plan listing use case."""

from apps.tasks.application.commands import ListDailyPlansCommand
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
from apps.tasks.domain.exceptions import TasksDomainError
from apps.tasks.domain.value_objects import UserId, normalize_date


class ListDailyPlans:
    """Return the daily plans of one user inside an inclusive date range."""

    def __init__(
        self,
        plans: DailyPlanRepository,
        tasks: TaskRepository,
        policy: PlanningPolicy = PLANNING_POLICY,
    ) -> None:
        self._plans = plans
        self._tasks = tasks
        self._policy = policy

    def execute(self, command: ListDailyPlansCommand) -> list[DailyPlanDetails]:
        try:
            user_id = UserId(command.user_id)
            start_date = normalize_date(command.start_date, label="Start date")
            end_date = normalize_date(command.end_date, label="End date")
            if start_date is None or end_date is None:
                raise ValueError("A date range requires both dates.")
            if start_date > end_date:
                raise ValueError("Start date cannot be after end date.")
        except (TasksDomainError, TypeError, ValueError) as error:
            raise InvalidTasksInput(str(error)) from error

        stored = self._plans.get_by_user_and_date_range(user_id, start_date, end_date)
        details: list[DailyPlanDetails] = []
        for plan in stored:
            details.append(
                daily_plan_details(
                    plan,
                    ordered_tasks(plan, self._tasks.get_by_ids(plan.task_ids)),
                    self._policy.overwhelmed_threshold,
                    self._policy.daily_plan_max_hours,
                )
            )
        return details
