"""Dashboard value-object and period-boundary tests."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("period", "value", "expected_start", "expected_end"),
    [
        (Period.DAILY, date(2025, 1, 15), date(2025, 1, 15), date(2025, 1, 15)),
        (Period.WEEKLY, date(2025, 1, 15), date(2025, 1, 13), date(2025, 1, 19)),
        (Period.MONTHLY, date(2025, 1, 15), date(2025, 1, 1), date(2025, 1, 31)),
        (Period.MONTHLY, date(2024, 2, 15), date(2024, 2, 1), date(2024, 2, 29)),
    ],
)
def test_period_normalizes_calendar_boundaries(
    period: Period,
    value: date,
    expected_start: date,
    expected_end: date,
) -> None:
    summary_date = SummaryDate(value)

    assert period.start(summary_date).value == expected_start
    assert period.end(summary_date).value == expected_end


@pytest.mark.parametrize(
    "value",
    [-Decimal("0.01"), Decimal("1.001"), Decimal("NaN"), Decimal("1E+30")],
)
def test_non_negative_totals_reject_invalid_amounts(value: Decimal) -> None:
    with pytest.raises(ValueError):
        TotalIncome(value)


def test_net_balance_can_be_negative() -> None:
    totals = PeriodTotals(
        income=TotalIncome(Decimal("10.00")),
        expense=TotalExpense(Decimal("25.50")),
        net_balance=NetBalance(Decimal("-15.50")),
    )

    assert totals.net_balance.amount == Decimal("-15.50")


def test_period_totals_require_consistent_net_balance() -> None:
    with pytest.raises(ValueError, match="income minus expenses"):
        PeriodTotals(
            income=TotalIncome(Decimal("10.00")),
            expense=TotalExpense(Decimal("2.00")),
            net_balance=NetBalance(Decimal("9.00")),
        )


def test_summary_date_rejects_datetime() -> None:
    with pytest.raises(ValueError, match="must be a date"):
        SummaryDate(datetime(2025, 1, 1))
