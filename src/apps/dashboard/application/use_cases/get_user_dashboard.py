"""Read pre-computed dashboard data for an authenticated user."""

from dataclasses import dataclass
from datetime import date as Date
from uuid import UUID

from apps.dashboard.application.dto import DashboardData
from apps.dashboard.application.exceptions import InvalidDashboardQuery
from apps.dashboard.application.ports.repositories import DashboardSummaryRepository
from apps.dashboard.domain.value_objects import Period, SummaryDate
from shared.domain.ports.clock import Clock

MAX_DASHBOARD_RANGE_DAYS = 366


@dataclass(frozen=True, slots=True)
class GetUserDashboardCommand:
    """Query parameters for a user's pre-computed dashboard summaries."""

    user_id: UUID
    period: Period
    start_date: Date | None = None
    end_date: Date | None = None


class GetUserDashboard:
    """Return a bounded range without calculating financial totals on read."""

    def __init__(
        self,
        repository: DashboardSummaryRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: GetUserDashboardCommand) -> DashboardData:
        """Load summaries, returning an empty collection when data is missing."""
        if not isinstance(command.period, Period):
            raise InvalidDashboardQuery("Dashboard period is invalid.")
        if not isinstance(command.user_id, UUID):
            raise InvalidDashboardQuery("Dashboard owner is invalid.")

        period = command.period
        today = SummaryDate(self._clock.today())
        raw_start, raw_end = self._resolve_dates(command, period, today)
        start = period.start(SummaryDate(raw_start))
        end = period.end(SummaryDate(raw_end))
        if end.value < start.value:
            raise InvalidDashboardQuery("Dashboard start date must not follow its end.")
        if (end.value - start.value).days + 1 > MAX_DASHBOARD_RANGE_DAYS:
            raise InvalidDashboardQuery(
                f"Dashboard ranges cannot exceed {MAX_DASHBOARD_RANGE_DAYS} days."
            )

        summaries = self._repository.list_for_user(
            command.user_id,
            period,
            start.value,
            end.value,
        )
        return DashboardData(
            period=period,
            start_date=start.value,
            end_date=end.value,
            summaries=tuple(summaries),
        )

    @staticmethod
    def _resolve_dates(
        command: GetUserDashboardCommand,
        period: Period,
        today: SummaryDate,
    ) -> tuple[Date, Date]:
        if command.start_date is None and command.end_date is None:
            return period.start(today).value, period.end(today).value
        if command.start_date is None:
            assert command.end_date is not None
            return command.end_date, command.end_date
        if command.end_date is None:
            return command.start_date, command.start_date
        return command.start_date, command.end_date
