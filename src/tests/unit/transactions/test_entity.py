"""Transaction aggregate business-rule tests."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.exceptions import FutureTransactionDate
from apps.transactions.domain.value_objects import (
    AccountId,
    Category,
    Money,
    TransactionDate,
    TransactionType,
)

from .fakes import FIXED_NOW

pytestmark = pytest.mark.unit


def _new_transaction(*, now: datetime = FIXED_NOW) -> Transaction:
    return Transaction.create(
        user_id=uuid4(),
        amount=Money(Decimal("25.00")),
        transaction_type=TransactionType.EXPENSE,
        category=Category("Food"),
        date=TransactionDate(date(2025, 1, 10)),
        description="Lunch",
        now=now,
    )


def test_transaction_starts_unidentified_and_can_be_updated() -> None:
    transaction = _new_transaction()
    later = datetime(2025, 1, 16, tzinfo=FIXED_NOW.tzinfo)

    assert transaction.id is None
    transaction.update(
        amount=Money(Decimal("75.25")),
        transaction_type=TransactionType.INVESTMENT,
        category=Category("Index fund"),
        date=TransactionDate(date(2025, 1, 15)),
        description=None,
        account_id=None,
        now=later,
    )

    assert transaction.amount.amount == Decimal("75.25")
    assert transaction.transaction_type is TransactionType.INVESTMENT
    assert transaction.category.value == "Index fund"
    assert transaction.description is None
    assert transaction.account_id is None
    assert transaction.updated_at == later


def test_transaction_update_replaces_and_clears_the_linked_account() -> None:
    account_id = AccountId(uuid4())
    transaction = _new_transaction()
    transaction.assign_account(account_id=account_id, now=FIXED_NOW)
    assert transaction.account_id == account_id

    transaction.update(
        amount=Money(Decimal("30.00")),
        transaction_type=TransactionType.EXPENSE,
        category=Category("Food"),
        date=TransactionDate(date(2025, 1, 10)),
        description="Lunch",
        account_id=None,
        now=FIXED_NOW,
    )

    assert transaction.account_id is None
    assert transaction.account_name is None


def test_transaction_assign_account_requires_an_account_identity() -> None:
    transaction = _new_transaction()

    with pytest.raises(TypeError, match="AccountId"):
        transaction.assign_account(
            account_id=str(uuid4()),  # type: ignore[arg-type]
            now=FIXED_NOW,
        )


def test_transaction_rejects_future_dates_on_create() -> None:
    with pytest.raises(FutureTransactionDate, match="future"):
        Transaction.create(
            user_id=uuid4(),
            amount=Money(Decimal("25.00")),
            transaction_type=TransactionType.EXPENSE,
            category=Category("Food"),
            date=TransactionDate(date(2025, 1, 16)),
            description=None,
            now=FIXED_NOW,
        )


def test_transaction_rejects_future_dates_on_update_without_mutation() -> None:
    transaction = _new_transaction()
    original_amount = transaction.amount

    with pytest.raises(FutureTransactionDate):
        transaction.update(
            amount=Money(Decimal("99.00")),
            transaction_type=TransactionType.EXPENSE,
            category=Category("Food"),
            date=TransactionDate(date(2025, 2, 1)),
            description=None,
            account_id=None,
            now=FIXED_NOW,
        )

    assert transaction.amount is original_amount


def test_transaction_requires_timezone_aware_clock_values() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _new_transaction(now=datetime(2025, 1, 15, 12))
