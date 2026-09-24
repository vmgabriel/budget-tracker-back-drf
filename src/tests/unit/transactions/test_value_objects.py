"""Transaction value-object tests."""

from dataclasses import FrozenInstanceError
from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)

pytestmark = pytest.mark.unit


def test_money_converts_and_preserves_decimal_value() -> None:
    money = Money(Decimal("125.50"))

    assert money.amount == Decimal("125.50")
    with pytest.raises(FrozenInstanceError):
        money.amount = Decimal("1.00")  # type: ignore[misc]


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-0.01")])
def test_money_rejects_non_positive_amounts(value: Decimal) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        Money(value)


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity")])
def test_money_rejects_non_finite_amounts(value: Decimal) -> None:
    with pytest.raises(ValueError, match="finite"):
        Money(value)


@pytest.mark.parametrize("value", [Decimal("0.001"), Decimal("1.234")])
def test_money_rejects_fractional_cents(value: Decimal) -> None:
    with pytest.raises(ValueError, match="two decimal places"):
        Money(value)


def test_money_enforces_storage_precision_bounds() -> None:
    assert Money(Decimal("0.01")).amount == Decimal("0.01")
    assert Money(Decimal("1.2300")).amount == Decimal("1.2300")
    assert Money(Decimal("9999999999.99")).amount == Decimal("9999999999.99")
    with pytest.raises(ValueError, match="9999999999.99"):
        Money(Decimal("10000000000.00"))


def test_category_collapses_whitespace() -> None:
    assert Category("  Food   and   Drink ").value == "Food and Drink"


@pytest.mark.parametrize("value", ["", "   ", "x" * 101])
def test_category_rejects_empty_or_oversized_values(value: str) -> None:
    with pytest.raises(ValueError):
        Category(value)


def test_transaction_date_requires_date_not_datetime() -> None:
    assert TransactionDate(date(2025, 1, 10)).value == date(2025, 1, 10)
    with pytest.raises(ValueError, match="must be a date"):
        TransactionDate(datetime(2025, 1, 10))


def test_transaction_id_wraps_uuid_and_rejects_other_values() -> None:
    transaction_id = uuid4()

    assert str(TransactionId(transaction_id)) == str(transaction_id)
    with pytest.raises(TypeError):
        TransactionId(str(transaction_id))  # type: ignore[arg-type]


def test_transaction_types_have_stable_api_values() -> None:
    assert [item.value for item in TransactionType] == [
        "income",
        "expense",
        "investment",
        "savings",
    ]
    assert TransactionType.EXPENSE.label == "Expense"
