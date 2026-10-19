"""Bounded transaction analytics use case.

The BFF needs chart-ready series, but the project forbids unbounded financial
aggregation on the request path. This use case accepts one bounded range, asks
the adapter for pre-aggregated rows, and formats them into flat chart data.
"""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from typing import cast
from uuid import UUID

from apps.transactions.application.analytics import (
    DEFAULT_PERIOD,
    GROUP_BY_CHOICES,
    GROUP_BY_TYPE,
    MAX_RANGE_DAYS,
    PERIOD_CHOICES,
    PERIOD_DAILY,
    PERIOD_WEEKLY,
    AnalyticsAggregate,
    CategoryTotal,
    TypeBucketTotals,
)
from apps.transactions.application.dto import (
    CategoryChartRow,
    TransactionAnalytics,
    TypeChartRow,
)
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.ports.repositories import TransactionRepository
from apps.transactions.domain.value_objects import CENT, TransactionType


@dataclass(frozen=True, slots=True)
class AnalyticsCommand:
    """Query parameters for one bounded analytics aggregation."""

    user_id: UUID
    start_date: Date
    end_date: Date
    group_by: str
    period: str = DEFAULT_PERIOD


class GetTransactionAnalytics:
    """Aggregate a bounded range into flat, chart-ready rows."""

    def __init__(self, repository: TransactionRepository) -> None:
        self._repository = repository

    def execute(self, command: AnalyticsCommand) -> TransactionAnalytics:
        start_date, end_date = self._validate_range(
            command.start_date, command.end_date
        )
        group_by = self._validate_group_by(command.group_by)
        period = self._validate_period(command.period)
        aggregates = self._repository.get_analytics_aggregates(
            command.user_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            period=period,
        )
        if group_by == GROUP_BY_TYPE:
            rows: tuple[TypeChartRow | CategoryChartRow, ...] = self._type_rows(
                aggregates, period
            )
        else:
            rows = self._category_rows(aggregates)
        return TransactionAnalytics(period=period, group_by=group_by, data=rows)

    @staticmethod
    def _validate_range(start_date: Date, end_date: Date) -> tuple[Date, Date]:
        if not isinstance(start_date, Date) or not isinstance(end_date, Date):
            raise InvalidTransactionInput("Analytics dates must be calendar dates.")
        if end_date < start_date:
            raise InvalidTransactionInput(
                "Analytics start_date must be on or before end_date."
            )
        if (end_date - start_date).days > MAX_RANGE_DAYS:
            raise InvalidTransactionInput(
                f"Analytics ranges cannot exceed {MAX_RANGE_DAYS} days."
            )
        return start_date, end_date

    @staticmethod
    def _validate_group_by(group_by: str) -> str:
        if group_by not in GROUP_BY_CHOICES:
            choices = ", ".join(GROUP_BY_CHOICES)
            raise InvalidTransactionInput(
                f"Analytics group_by must be one of: {choices}."
            )
        return group_by

    @staticmethod
    def _validate_period(period: str) -> str:
        if period not in PERIOD_CHOICES:
            choices = ", ".join(PERIOD_CHOICES)
            raise InvalidTransactionInput(
                f"Analytics period must be one of: {choices}."
            )
        return period

    def _type_rows(
        self, aggregates: list[AnalyticsAggregate], period: str
    ) -> tuple[TypeChartRow, ...]:
        totals = cast(list[TypeBucketTotals], aggregates)
        return tuple(
            TypeChartRow(
                label=_bucket_label(row.bucket, period),
                income=_amount(row.totals.get(TransactionType.INCOME, Decimal("0"))),
                expense=_amount(row.totals.get(TransactionType.EXPENSE, Decimal("0"))),
                investment=_amount(
                    row.totals.get(TransactionType.INVESTMENT, Decimal("0"))
                ),
                savings=_amount(row.totals.get(TransactionType.SAVINGS, Decimal("0"))),
            )
            for row in totals
        )

    def _category_rows(
        self, aggregates: list[AnalyticsAggregate]
    ) -> tuple[CategoryChartRow, ...]:
        totals = cast(list[CategoryTotal], aggregates)
        return tuple(
            CategoryChartRow(label=row.category, total=_amount(row.total))
            for row in totals
        )


def _bucket_label(bucket: Date, period: str) -> str:
    """Render one bucket start as a stable, frontend-friendly label."""
    if period == PERIOD_DAILY:
        return bucket.isoformat()
    if period == PERIOD_WEEKLY:
        iso_year, iso_week, _ = bucket.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    return f"{bucket.year:04d}-{bucket.month:02d}"


def _amount(value: Decimal) -> str:
    """Quantize a monetary total to the two decimals charts expect."""
    return str(value.quantize(CENT))


__all__ = ("AnalyticsCommand", "GetTransactionAnalytics")
