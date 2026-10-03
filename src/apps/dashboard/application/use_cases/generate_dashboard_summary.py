"""Generate one pre-computed dashboard summary from lower-level summaries."""

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from apps.dashboard.application.exceptions import InvalidDashboardCommand
from apps.dashboard.application.ports.repositories import (
    DashboardSummaryRepository,
    TransactionRepository,
)
from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
    is_valid_timezone,
    utc_to_local_date,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class GenerateDashboardSummaryCommand:
    """Input for calculating a daily, weekly, or monthly summary."""

    user_id: UUID
    period: Period
    summary_date: Date
    user_timezone: str = "UTC"


class GenerateDashboardSummary:
    """Calculate and persist one idempotent dashboard summary snapshot."""

    def __init__(
        self,
        summary_repository: DashboardSummaryRepository,
        transaction_repository: TransactionRepository,
        clock: Clock,
    ) -> None:
        self._summary_repository = summary_repository
        self._transaction_repository = transaction_repository
        self._clock = clock

    def execute(
        self,
        command: GenerateDashboardSummaryCommand,
    ) -> DashboardSummary:
        """Generate a summary from transactions or child period summaries."""
        if not isinstance(command.user_id, UUID):
            raise InvalidDashboardCommand("Dashboard owner is invalid.")
        if not isinstance(command.period, Period):
            raise InvalidDashboardCommand("Dashboard period is invalid.")
        if not isinstance(command.summary_date, Date) or isinstance(
            command.summary_date, datetime
        ):
            raise InvalidDashboardCommand("Dashboard summary date is invalid.")
        if not is_valid_timezone(command.user_timezone):
            raise InvalidDashboardCommand("Dashboard timezone is invalid.")

        period = command.period
        local_today = utc_to_local_date(self._clock.now(), command.user_timezone)
        summary_date = period.start(SummaryDate(command.summary_date))
        if period is Period.DAILY:
            totals = self._transaction_repository.aggregate_totals(
                command.user_id,
                summary_date.value,
                summary_date.value,
            )
            is_stale = False
        elif period is Period.WEEKLY:
            totals, is_complete = self._weekly_totals(
                command.user_id,
                summary_date,
                local_today,
            )
            is_stale = not is_complete
        else:
            totals, is_complete = self._monthly_totals(
                command.user_id,
                summary_date,
                local_today,
            )
            is_stale = not is_complete

        generated_at = self._clock.now()
        existing = self._summary_repository.get(
            command.user_id,
            period,
            summary_date,
        )
        if existing is not None:
            summary = existing.replace(
                totals=totals,
                generated_at=generated_at,
                is_stale=is_stale,
            )
        else:
            summary = DashboardSummary.create(
                user_id=command.user_id,
                period=period,
                summary_date=summary_date,
                totals=totals,
                generated_at=generated_at,
                is_stale=is_stale,
                stale_at=generated_at if is_stale else None,
            )
        return self._summary_repository.save(summary)

    def _weekly_totals(
        self,
        user_id: UUID,
        summary_date: SummaryDate,
        today: Date,
    ) -> tuple[PeriodTotals, bool]:
        end = Period.WEEKLY.end(summary_date)
        expected_through = min(end.value, today)
        daily = self._summary_repository.list_for_user(
            user_id,
            Period.DAILY,
            summary_date.value,
            end.value,
        )
        by_date = {item.summary_date.value: item for item in daily}
        income = Decimal("0.00")
        expense = Decimal("0.00")
        is_complete = True
        cursor = summary_date.value
        while cursor <= expected_through:
            item = by_date.get(cursor)
            if item is None or item.is_stale:
                is_complete = False
            if item is not None:
                income += item.total_income.amount
                expense += item.total_expense.amount
            cursor += timedelta(days=1)
        return _totals(income, expense), is_complete

    def _monthly_totals(
        self,
        user_id: UUID,
        summary_date: SummaryDate,
        today: Date,
    ) -> tuple[PeriodTotals, bool]:
        month_end = Period.MONTHLY.end(summary_date)
        first_week = summary_date.value - timedelta(days=summary_date.value.weekday())
        last_week = month_end.value - timedelta(days=month_end.value.weekday())
        weekly = self._summary_repository.list_for_user(
            user_id,
            Period.WEEKLY,
            first_week,
            last_week,
        )
        weekly_by_date = {item.summary_date.value: item for item in weekly}

        income = Decimal("0.00")
        expense = Decimal("0.00")
        is_complete = True
        cursor = first_week
        while cursor <= min(last_week, today):
            week_start = cursor
            week_end = cursor + timedelta(days=6)
            overlap_start = max(week_start, summary_date.value)
            overlap_end = min(week_end, month_end.value)
            if overlap_start == week_start and overlap_end == week_end:
                # Full interior weeks use their pre-computed weekly totals.
                week = weekly_by_date.get(cursor)
                if week is None or week.is_stale:
                    is_complete = False
                if week is not None:
                    income += week.total_income.amount
                    expense += week.total_expense.amount
            else:
                # ISO weeks crossing a month boundary are clipped using daily
                # rows so totals never include transactions from adjacent months.
                boundary_income, boundary_expense, boundary_complete = (
                    self._daily_range_totals(
                        user_id,
                        overlap_start,
                        overlap_end,
                        today,
                    )
                )
                income += boundary_income
                expense += boundary_expense
                is_complete = is_complete and boundary_complete
            cursor += timedelta(days=7)
        return _totals(income, expense), is_complete

    def _daily_range_totals(
        self,
        user_id: UUID,
        start: Date,
        end: Date,
        today: Date,
    ) -> tuple[Decimal, Decimal, bool]:
        daily = self._summary_repository.list_for_user(
            user_id,
            Period.DAILY,
            start,
            end,
        )
        by_date = {item.summary_date.value: item for item in daily}
        income = Decimal("0.00")
        expense = Decimal("0.00")
        is_complete = True
        cursor = start
        expected_through = min(end, today)
        while cursor <= expected_through:
            item = by_date.get(cursor)
            if item is None or item.is_stale:
                is_complete = False
            if item is not None:
                income += item.total_income.amount
                expense += item.total_expense.amount
            cursor += timedelta(days=1)
        return income, expense, is_complete


def _totals(income: Decimal, expense: Decimal) -> PeriodTotals:
    return PeriodTotals(
        income=TotalIncome(income),
        expense=TotalExpense(expense),
        net_balance=NetBalance(income - expense),
    )
