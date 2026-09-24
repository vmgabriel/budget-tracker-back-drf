"""Return current dashboard snapshots without calculating totals on read."""

from datetime import date
from uuid import UUID

from apps.dashboard.application.dto import DashboardOverview
from apps.dashboard.application.exceptions import InvalidDashboardQuery
from apps.dashboard.application.ports.repositories import DashboardSummaryRepository
from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import Period, SummaryDate
from shared.domain.ports.clock import Clock


class GetDashboardOverview:
    """Load today's, this week's, and this month's persisted summaries."""

    def __init__(
        self,
        repository: DashboardSummaryRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, user_id: UUID) -> DashboardOverview:
        """Return current snapshots, using null for data still being generated."""
        if not isinstance(user_id, UUID):
            raise InvalidDashboardQuery("Dashboard owner is invalid.")

        today = self._clock.today()
        return DashboardOverview(
            as_of_date=today,
            today=self._get_current(user_id, Period.DAILY, today),
            this_week=self._get_current(user_id, Period.WEEKLY, today),
            this_month=self._get_current(user_id, Period.MONTHLY, today),
        )

    def _get_current(
        self,
        user_id: UUID,
        period: Period,
        today: date,
    ) -> DashboardSummary | None:
        summary_date = period.start(SummaryDate(today))
        return self._repository.get(user_id, period, summary_date)
