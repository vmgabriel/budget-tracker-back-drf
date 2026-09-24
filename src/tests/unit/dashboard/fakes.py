"""In-memory test doubles for dashboard ports."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
)

FIXED_NOW = datetime(2025, 1, 15, 12, tzinfo=UTC)


class FakeClock:
    """Return a deterministic timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


class FakeDashboardSummaryRepository:
    """Store immutable summaries in memory by natural key."""

    def __init__(self) -> None:
        self.summaries: dict[tuple[UUID, Period, date], DashboardSummary] = {}
        self.stale_calls: list[set[tuple[Period, SummaryDate]]] = []

    def get(
        self,
        user_id: UUID,
        period: Period,
        summary_date: SummaryDate,
    ) -> DashboardSummary | None:
        return self.summaries.get((user_id, period, summary_date.value))

    def list_for_user(
        self,
        user_id: UUID,
        period: Period,
        start_date: date,
        end_date: date,
    ) -> list[DashboardSummary]:
        return sorted(
            (
                summary
                for (owner_id, item_period, summary_date), summary in (
                    self.summaries.items()
                )
                if owner_id == user_id
                and item_period == period
                and start_date <= summary_date <= end_date
            ),
            key=lambda summary: summary.summary_date.value,
        )

    def save(self, summary: DashboardSummary) -> DashboardSummary:
        self.summaries[
            (summary.user_id, summary.period, summary.summary_date.value)
        ] = summary
        return summary

    def mark_stale(
        self,
        user_id: UUID,
        periods: set[tuple[Period, SummaryDate]],
        stale_at: datetime,
    ) -> int:
        self.stale_calls.append(periods)
        changed = 0
        for key, summary in self.summaries.items():
            owner_id, period, summary_date = key
            if (
                owner_id == user_id
                and not summary.is_stale
                and (period, SummaryDate(summary_date)) in periods
            ):
                self.summaries[key] = summary.mark_stale(stale_at)
                changed += 1
        return changed


class FakeTransactionRepository:
    """Return configured totals for every requested daily range."""

    def __init__(self, totals: PeriodTotals | None = None) -> None:
        self.totals = totals or _totals(Decimal("0.00"), Decimal("0.00"))
        self.calls: list[tuple[UUID, date, date]] = []

    def aggregate_totals(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PeriodTotals:
        self.calls.append((user_id, start_date, end_date))
        return self.totals


def make_summary(
    *,
    user_id: UUID,
    period: Period,
    summary_date: date,
    income: Decimal = Decimal("0.00"),
    expense: Decimal = Decimal("0.00"),
    generated_at: datetime = FIXED_NOW,
    is_stale: bool = False,
    normalize: bool = True,
) -> DashboardSummary:
    """Build a persisted summary for application tests."""
    return DashboardSummary.create(
        user_id=user_id,
        period=period,
        summary_date=(
            period.start(SummaryDate(summary_date))
            if normalize
            else SummaryDate(summary_date)
        ),
        totals=_totals(income, expense),
        generated_at=generated_at,
        is_stale=is_stale,
        stale_at=generated_at if is_stale else None,
    )


def _totals(income: Decimal, expense: Decimal) -> PeriodTotals:
    return PeriodTotals(
        income=TotalIncome(income),
        expense=TotalExpense(expense),
        net_balance=NetBalance(income - expense),
    )
