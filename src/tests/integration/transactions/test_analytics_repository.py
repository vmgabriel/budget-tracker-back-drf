"""Django ORM adapter tests for transaction analytics aggregates."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from apps.transactions.application.analytics import CategoryTotal, TypeBucketTotals
from apps.transactions.domain.value_objects import TransactionType
from apps.transactions.infrastructure.persistence.repositories import (
    DjangoTransactionRepository,
)
from tests.factories import TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

START = date(2025, 1, 1)
END = date(2025, 2, 28)


def _seed() -> tuple[Any, Any]:
    """Create a two-month ledger plus rows that must stay out of the result."""
    owner: Any = UserFactory()
    other: Any = UserFactory()
    rows = (
        (owner, date(2025, 1, 6), TransactionType.EXPENSE, "Food", "10.00"),
        (owner, date(2025, 1, 8), TransactionType.EXPENSE, "Food", "20.00"),
        (owner, date(2025, 1, 20), TransactionType.EXPENSE, "Rent", "800.00"),
        (owner, date(2025, 2, 3), TransactionType.INCOME, "Salary", "1000.00"),
        (owner, date(2025, 2, 4), TransactionType.INVESTMENT, "Index", "200.00"),
        (owner, date(2025, 2, 5), TransactionType.SAVINGS, "Emergency", "50.00"),
        # Foreign owner and out-of-range row: neither may leak into analytics.
        (other, date(2025, 1, 6), TransactionType.EXPENSE, "Food", "999.00"),
        (owner, date(2024, 12, 30), TransactionType.EXPENSE, "Food", "5.00"),
    )
    for user, day, kind, category, amount in rows:
        TransactionFactory(
            user=user,
            date=day,
            transaction_type=kind.value,
            category=category,
            amount=Decimal(amount),
        )
    return owner, other


def _totals(**values: str) -> dict[TransactionType, Decimal]:
    amounts = {kind: Decimal("0.00") for kind in TransactionType}
    amounts.update(
        {
            TransactionType[name.upper()]: Decimal(value)
            for name, value in values.items()
        }
    )
    return amounts


def test_monthly_type_aggregates_fold_all_series_per_bucket() -> None:
    owner, _ = _seed()

    rows = DjangoTransactionRepository().get_analytics_aggregates(
        owner.id,
        start_date=START,
        end_date=END,
        group_by="type",
        period="monthly",
    )

    assert rows == [
        TypeBucketTotals(
            bucket=date(2025, 1, 1),
            totals=_totals(expense="830.00"),
        ),
        TypeBucketTotals(
            bucket=date(2025, 2, 1),
            totals=_totals(income="1000.00", investment="200.00", savings="50.00"),
        ),
    ]


def test_weekly_type_aggregates_use_iso_mondays() -> None:
    owner, _ = _seed()

    rows = DjangoTransactionRepository().get_analytics_aggregates(
        owner.id,
        start_date=START,
        end_date=END,
        group_by="type",
        period="weekly",
    )

    assert rows == [
        TypeBucketTotals(bucket=date(2025, 1, 6), totals=_totals(expense="30.00")),
        TypeBucketTotals(bucket=date(2025, 1, 20), totals=_totals(expense="800.00")),
        TypeBucketTotals(
            bucket=date(2025, 2, 3),
            totals=_totals(income="1000.00", investment="200.00", savings="50.00"),
        ),
    ]


def test_daily_type_aggregates_are_chronological_and_bounded() -> None:
    owner, _ = _seed()

    rows = DjangoTransactionRepository().get_analytics_aggregates(
        owner.id,
        start_date=START,
        end_date=END,
        group_by="type",
        period="daily",
    )

    assert [row.bucket for row in rows if isinstance(row, TypeBucketTotals)] == [
        date(2025, 1, 6),
        date(2025, 1, 8),
        date(2025, 1, 20),
        date(2025, 2, 3),
        date(2025, 2, 4),
        date(2025, 2, 5),
    ]
    assert rows[0] == TypeBucketTotals(
        bucket=date(2025, 1, 6),
        totals=_totals(expense="10.00"),
    )


def test_category_aggregates_cover_expenses_only_largest_first() -> None:
    owner, _ = _seed()

    rows = DjangoTransactionRepository().get_analytics_aggregates(
        owner.id,
        start_date=START,
        end_date=END,
        group_by="category",
        period="monthly",
    )

    # Rent (800.00) before Food (30.00); income/investment/savings categories,
    # the other owner, and the out-of-range row are all excluded.
    assert rows == [
        CategoryTotal(category="Rent", total=Decimal("800.00")),
        CategoryTotal(category="Food", total=Decimal("30.00")),
    ]


def test_category_aggregates_are_owner_scoped() -> None:
    _, other = _seed()

    rows = DjangoTransactionRepository().get_analytics_aggregates(
        other.id,
        start_date=START,
        end_date=END,
        group_by="category",
        period="monthly",
    )

    assert rows == [CategoryTotal(category="Food", total=Decimal("999.00"))]
