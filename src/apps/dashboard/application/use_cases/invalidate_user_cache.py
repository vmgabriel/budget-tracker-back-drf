"""Invalidate dashboard summaries affected by transaction changes."""

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime
from uuid import UUID

from apps.dashboard.application.exceptions import InvalidDashboardCommand
from apps.dashboard.application.ports.repositories import DashboardSummaryRepository
from apps.dashboard.domain.value_objects import Period, SummaryDate
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class InvalidateUserCacheCommand:
    """Transaction dates and the summary granularities to mark stale.

    Transaction lifecycle invalidation defaults to every granularity. Rollup
    tasks can limit boundary cleanup to daily rows when parent periods belong
    to a different calendar month.
    """

    user_id: UUID
    affected_dates: tuple[Date, ...]
    periods: tuple[Period, ...] = tuple(Period)


class InvalidateUserCache:
    """Mark affected pre-computed summaries as stale."""

    def __init__(
        self,
        repository: DashboardSummaryRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: InvalidateUserCacheCommand) -> int:
        """Invalidate all period rows touched by the supplied transaction dates."""
        if not isinstance(command.user_id, UUID):
            raise InvalidDashboardCommand("Dashboard owner is invalid.")
        if any(
            not isinstance(value, Date) or isinstance(value, datetime)
            for value in command.affected_dates
        ):
            raise InvalidDashboardCommand("Affected transaction dates are invalid.")
        if not command.periods or any(
            not isinstance(period, Period) for period in command.periods
        ):
            raise InvalidDashboardCommand("Invalidation periods are invalid.")

        period_keys: set[tuple[Period, SummaryDate]] = set()
        for affected_date in set(command.affected_dates):
            summary_date = SummaryDate(affected_date)
            for period in command.periods:
                period_keys.add((period, period.start(summary_date)))
        stale_at = self._clock.now()
        return self._repository.mark_stale(command.user_id, period_keys, stale_at)
