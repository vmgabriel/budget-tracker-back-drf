"""Application-level configuration for the tasks bounded context.

The domain validates *what* a valid hour estimate is; this module chooses the
*values* the product starts with. In Phase 2 these two numbers become
per-user preferences read from the profile, which is why they live outside the
domain and reach use cases through an injected ``PlanningPolicy``.
"""

from dataclasses import dataclass
from decimal import Decimal

from apps.tasks.domain.value_objects import Duration, OverwhelmedThreshold

TASKS_DEFAULTS: dict[str, Decimal] = {
    "OVERWHELMED_THRESHOLD_HOURS": Decimal("4.0"),
    "DAILY_PLAN_MAX_HOURS": Decimal("8.0"),
}


@dataclass(frozen=True, slots=True)
class PlanningPolicy:
    """Hour budgets applied when a user has not chosen their own.

    ``overwhelmed_threshold`` flags a single task as too big to face at once;
    ``daily_plan_max_hours`` caps how much work fits in one day.
    """

    overwhelmed_threshold: OverwhelmedThreshold
    daily_plan_max_hours: Duration


PLANNING_POLICY = PlanningPolicy(
    overwhelmed_threshold=OverwhelmedThreshold(
        TASKS_DEFAULTS["OVERWHELMED_THRESHOLD_HOURS"]
    ),
    daily_plan_max_hours=Duration(TASKS_DEFAULTS["DAILY_PLAN_MAX_HOURS"]),
)
