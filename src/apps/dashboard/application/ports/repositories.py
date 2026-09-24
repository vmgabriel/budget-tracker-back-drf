"""Persistence ports for dashboard pre-computed summaries."""

from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import Period, PeriodTotals, SummaryDate


class DashboardSummaryRepository(Protocol):
    """Storage operations required by dashboard application use cases."""

    def get(
        self,
        user_id: UUID,
        period: Period,
        summary_date: SummaryDate,
    ) -> DashboardSummary | None:
        """Return one exact period summary when it exists."""
        raise NotImplementedError()

    def list_for_user(
        self,
        user_id: UUID,
        period: Period,
        start_date: date,
        end_date: date,
    ) -> list[DashboardSummary]:
        """Return persisted summaries whose period starts in the date range."""
        raise NotImplementedError()

    def save(self, summary: DashboardSummary) -> DashboardSummary:
        """Insert or replace a summary by its natural idempotency key."""
        raise NotImplementedError()

    def mark_stale(
        self,
        user_id: UUID,
        periods: set[tuple[Period, SummaryDate]],
        stale_at: datetime,
    ) -> int:
        """Mark the selected summaries stale and return the changed row count."""
        raise NotImplementedError()


class TransactionRepository(Protocol):
    """Read-only transaction access needed to calculate daily summaries."""

    def aggregate_totals(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PeriodTotals:
        """Aggregate income and expenses in an inclusive date range."""
        raise NotImplementedError()
