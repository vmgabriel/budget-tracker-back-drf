"""DashboardSummary immutability tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.exceptions import (
    DashboardSummaryImmutable,
    InvalidDashboardSummary,
)
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
)

from .fakes import FIXED_NOW, make_summary

pytestmark = pytest.mark.unit


def test_fresh_closed_period_summary_cannot_be_replaced() -> None:
    summary = make_summary(
        user_id=uuid4(),
        period=Period.DAILY,
        summary_date=date(2025, 1, 10),
    )

    with pytest.raises(DashboardSummaryImmutable):
        summary.replace(
            totals=_totals(Decimal("50.00"), Decimal("0.00")),
            generated_at=FIXED_NOW,
        )


def test_stale_summary_can_be_replaced_without_mutating_original() -> None:
    original = make_summary(
        user_id=uuid4(),
        period=Period.DAILY,
        summary_date=date(2025, 1, 10),
        income=Decimal("25.00"),
    )
    stale = original.mark_stale(FIXED_NOW)

    replacement = stale.replace(
        totals=_totals(Decimal("50.00"), Decimal("0.00")),
        generated_at=FIXED_NOW,
    )

    assert original.total_income.amount == Decimal("25.00")
    assert replacement.total_income.amount == Decimal("50.00")
    assert not replacement.is_stale


def test_marking_an_already_stale_summary_is_idempotent() -> None:
    summary = make_summary(
        user_id=uuid4(),
        period=Period.DAILY,
        summary_date=date(2025, 1, 10),
        is_stale=True,
    )

    assert summary.mark_stale(FIXED_NOW) is summary


def test_summary_date_must_be_a_normalized_period_start() -> None:
    with pytest.raises(InvalidDashboardSummary, match="normalized"):
        make_summary(
            user_id=uuid4(),
            period=Period.WEEKLY,
            summary_date=date(2025, 1, 15),
            normalize=False,
        )


def test_summary_requires_consistent_stale_timestamp() -> None:
    with pytest.raises(InvalidDashboardSummary, match="require stale_at"):
        DashboardSummary.create(
            user_id=uuid4(),
            period=Period.DAILY,
            summary_date=SummaryDate(date(2025, 1, 10)),
            totals=_totals(Decimal("0.00"), Decimal("0.00")),
            generated_at=FIXED_NOW,
            stale_at=FIXED_NOW,
        )


def _totals(income: Decimal, expense: Decimal) -> PeriodTotals:
    return PeriodTotals(
        income=TotalIncome(income),
        expense=TotalExpense(expense),
        net_balance=NetBalance(income - expense),
    )
