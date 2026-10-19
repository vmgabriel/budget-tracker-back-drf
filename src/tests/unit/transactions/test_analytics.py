"""Analytics use-case tests: validation, labels, and chart formatting."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.transactions.application.analytics import CategoryTotal, TypeBucketTotals
from apps.transactions.application.dto import (
    CategoryChartRow,
    TransactionAnalytics,
    TypeChartRow,
)
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.use_cases import (
    AnalyticsCommand,
    GetTransactionAnalytics,
)
from apps.transactions.domain.value_objects import TransactionType

from .fakes import FakeTransactionRepository

pytestmark = pytest.mark.unit

START = date(2025, 1, 1)
END = date(2025, 1, 31)


def _command(
    *,
    user_id: UUID | None = None,
    start_date: date = START,
    end_date: date = END,
    group_by: str = "type",
    period: str = "monthly",
) -> AnalyticsCommand:
    return AnalyticsCommand(
        user_id=user_id or uuid4(),
        start_date=start_date,
        end_date=end_date,
        group_by=group_by,
        period=period,
    )


def test_daily_type_rows_are_flat_and_zero_fill_missing_types() -> None:
    repository = FakeTransactionRepository(
        [
            TypeBucketTotals(
                bucket=date(2025, 1, 6),
                totals={
                    TransactionType.INCOME: Decimal("100.00"),
                    TransactionType.EXPENSE: Decimal("30.50"),
                },
            )
        ]
    )

    result = GetTransactionAnalytics(repository).execute(_command(period="daily"))

    assert result == TransactionAnalytics(
        period="daily",
        group_by="type",
        data=(
            TypeChartRow(
                label="2025-01-06",
                income="100.00",
                expense="30.50",
                investment="0.00",
                savings="0.00",
            ),
        ),
    )


@pytest.mark.parametrize(
    ("bucket", "period", "label"),
    [
        (date(2025, 1, 6), "weekly", "2025-W02"),
        (date(2025, 12, 29), "weekly", "2026-W01"),
        (date(2025, 1, 1), "monthly", "2025-01"),
        (date(2025, 11, 30), "monthly", "2025-11"),
        (date(2025, 2, 3), "daily", "2025-02-03"),
    ],
)
def test_bucket_labels_are_stable_across_periods(
    bucket: date, period: str, label: str
) -> None:
    repository = FakeTransactionRepository([TypeBucketTotals(bucket=bucket, totals={})])

    result = GetTransactionAnalytics(repository).execute(_command(period=period))

    row = result.data[0]
    assert isinstance(row, TypeChartRow)
    assert row.label == label


def test_category_rows_keep_repository_order_and_format_totals() -> None:
    repository = FakeTransactionRepository(
        [
            CategoryTotal(category="Rent", total=Decimal("800.00")),
            CategoryTotal(category="Food", total=Decimal("150.5")),
        ]
    )

    result = GetTransactionAnalytics(repository).execute(_command(group_by="category"))

    assert result == TransactionAnalytics(
        period="monthly",
        group_by="category",
        data=(
            CategoryChartRow(label="Rent", total="800.00"),
            CategoryChartRow(label="Food", total="150.50"),
        ),
    )


def test_command_is_forwarded_to_the_repository_unchanged() -> None:
    owner_id = uuid4()
    repository = FakeTransactionRepository()

    GetTransactionAnalytics(repository).execute(
        _command(user_id=owner_id, group_by="type", period="weekly")
    )

    assert repository.analytics_calls == [
        {
            "user_id": owner_id,
            "start_date": START,
            "end_date": END,
            "group_by": "type",
            "period": "weekly",
        }
    ]


def test_period_defaults_to_monthly() -> None:
    repository = FakeTransactionRepository()

    result = GetTransactionAnalytics(repository).execute(
        AnalyticsCommand(
            user_id=uuid4(),
            start_date=START,
            end_date=END,
            group_by="type",
        )
    )

    assert result.period == "monthly"
    assert repository.analytics_calls[0]["period"] == "monthly"


def test_a_range_of_exactly_366_days_is_accepted() -> None:
    repository = FakeTransactionRepository()

    result = GetTransactionAnalytics(repository).execute(
        _command(start_date=date(2025, 1, 1), end_date=date(2026, 1, 2))
    )

    assert result.data == ()
    assert len(repository.analytics_calls) == 1


def test_a_range_longer_than_366_days_is_rejected() -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput, match="366"):
        GetTransactionAnalytics(repository).execute(
            _command(start_date=date(2025, 1, 1), end_date=date(2026, 1, 3))
        )

    assert repository.analytics_calls == []


def test_a_reversed_range_is_rejected() -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput, match="start_date"):
        GetTransactionAnalytics(repository).execute(
            _command(start_date=END, end_date=START)
        )

    assert repository.analytics_calls == []


def test_unknown_group_by_is_rejected_before_querying() -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput, match="group_by"):
        GetTransactionAnalytics(repository).execute(_command(group_by="account"))

    assert repository.analytics_calls == []


def test_unknown_period_is_rejected_before_querying() -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput, match="period"):
        GetTransactionAnalytics(repository).execute(_command(period="yearly"))

    assert repository.analytics_calls == []
