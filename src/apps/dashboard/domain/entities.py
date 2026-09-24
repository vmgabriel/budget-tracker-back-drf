"""The dashboard summary aggregate and its immutability rules."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.dashboard.domain.exceptions import (
    DashboardSummaryImmutable,
    InvalidDashboardSummary,
)
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    SummaryId,
    TotalExpense,
    TotalIncome,
)


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """An immutable snapshot of one user's totals for a calendar period."""

    user_id: UUID
    period: Period
    summary_date: SummaryDate
    total_income: TotalIncome
    total_expense: TotalExpense
    net_balance: NetBalance
    generated_at: datetime
    is_stale: bool = False
    stale_at: datetime | None = None
    id: SummaryId | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        period: Period,
        summary_date: SummaryDate,
        totals: PeriodTotals,
        generated_at: datetime,
        is_stale: bool = False,
        stale_at: datetime | None = None,
        id: SummaryId | None = None,
    ) -> "DashboardSummary":
        """Create a validated period summary."""
        if not isinstance(user_id, UUID):
            raise TypeError("Dashboard summary owner must be identified by a UUID.")
        if not isinstance(period, Period):
            raise InvalidDashboardSummary("Dashboard summary period is invalid.")
        if summary_date != period.start(summary_date):
            raise InvalidDashboardSummary(
                "Dashboard summary date must be normalized to its period."
            )
        cls._validate_timestamp(generated_at, "generated_at")
        if stale_at is not None:
            cls._validate_timestamp(stale_at, "stale_at")
        if is_stale != (stale_at is not None):
            raise InvalidDashboardSummary(
                "Stale summaries require stale_at and fresh summaries cannot have it."
            )
        if id is not None and not isinstance(id, SummaryId):
            raise TypeError("Dashboard summary identity is invalid.")
        return cls(
            user_id=user_id,
            period=period,
            summary_date=summary_date,
            total_income=totals.income,
            total_expense=totals.expense,
            net_balance=totals.net_balance,
            generated_at=generated_at,
            is_stale=is_stale,
            stale_at=stale_at,
            id=id,
        )

    def mark_stale(self, stale_at: datetime) -> "DashboardSummary":
        """Mark the snapshot stale without changing its financial values."""
        self._validate_timestamp(stale_at, "stale_at")
        if self.is_stale and self.stale_at is not None:
            return self
        return DashboardSummary(
            user_id=self.user_id,
            period=self.period,
            summary_date=self.summary_date,
            total_income=self.total_income,
            total_expense=self.total_expense,
            net_balance=self.net_balance,
            generated_at=self.generated_at,
            is_stale=True,
            stale_at=stale_at,
            id=self.id,
        )

    def replace(
        self,
        *,
        totals: PeriodTotals,
        generated_at: datetime,
        is_stale: bool = False,
    ) -> "DashboardSummary":
        """Replace a current or explicitly stale snapshot with calculated totals."""
        self._validate_timestamp(generated_at, "generated_at")
        if not self.is_stale and self.is_closed_at(generated_at):
            raise DashboardSummaryImmutable(
                "A fresh dashboard summary for a closed period is immutable."
            )
        return DashboardSummary.create(
            user_id=self.user_id,
            period=self.period,
            summary_date=self.summary_date,
            totals=totals,
            generated_at=generated_at,
            is_stale=is_stale,
            stale_at=generated_at if is_stale else None,
            id=self.id,
        )

    def is_closed_at(self, moment: datetime) -> bool:
        """Return whether this summary's calendar period has ended."""
        self._validate_timestamp(moment, "moment")
        return self.period.end(self.summary_date).value < moment.date()

    @property
    def status(self) -> str:
        """Return the interface-safe freshness status."""
        return "stale" if self.is_stale else "fresh"

    @staticmethod
    def _validate_timestamp(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"Summary {field_name} must be timezone-aware.")
