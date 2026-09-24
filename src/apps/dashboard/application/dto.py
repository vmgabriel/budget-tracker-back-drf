"""Application-layer results safe to expose through interfaces."""

from dataclasses import dataclass
from datetime import date

from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import Period


@dataclass(frozen=True, slots=True)
class DashboardData:
    """A bounded collection of pre-computed summaries."""

    period: Period
    start_date: date
    end_date: date
    summaries: tuple[DashboardSummary, ...]

    @property
    def has_stale_data(self) -> bool:
        """Return whether at least one result requires regeneration."""
        return any(summary.is_stale for summary in self.summaries)


@dataclass(frozen=True, slots=True)
class DashboardOverview:
    """The three current pre-computed snapshots shown on an overview page."""

    as_of_date: date
    today: DashboardSummary | None
    this_week: DashboardSummary | None
    this_month: DashboardSummary | None
