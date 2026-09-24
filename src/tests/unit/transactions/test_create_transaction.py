"""CreateTransaction use-case tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.use_cases import (
    CreateTransaction,
    CreateTransactionCommand,
)
from apps.transactions.domain.value_objects import TransactionType

from .fakes import FakeClock, FakeTransactionRepository

pytestmark = pytest.mark.unit


def _command(**overrides: object) -> CreateTransactionCommand:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "amount": Decimal("25.00"),
        "transaction_type": TransactionType.EXPENSE,
        "category": "  Food   and   Drink ",
        "date": date(2025, 1, 10),
        "description": "  Lunch  ",
    }
    values.update(overrides)
    return CreateTransactionCommand(**values)  # type: ignore[arg-type]


def test_create_transaction_normalizes_and_returns_safe_details() -> None:
    repository = FakeTransactionRepository()
    clock = FakeClock()

    result = CreateTransaction(repository, clock).execute(_command())

    assert result.amount == Decimal("25.00")
    assert result.category == "Food and Drink"
    assert result.description == "Lunch"
    assert result.created_at == clock.now()
    assert result.updated_at == clock.now()
    assert len(repository.transactions) == 1


def test_create_transaction_rejects_non_positive_amount() -> None:
    with pytest.raises(InvalidTransactionInput, match="greater than zero"):
        CreateTransaction(FakeTransactionRepository(), FakeClock()).execute(
            _command(amount=Decimal("0.00"))
        )


@pytest.mark.parametrize(
    "amount",
    [Decimal("1.001"), Decimal("10000000000.00")],
)
def test_create_transaction_rejects_amounts_outside_storage_precision(
    amount: Decimal,
) -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput):
        CreateTransaction(repository, FakeClock()).execute(_command(amount=amount))

    assert not repository.transactions


def test_create_transaction_rejects_future_date_using_injected_clock() -> None:
    with pytest.raises(InvalidTransactionInput, match="future"):
        CreateTransaction(FakeTransactionRepository(), FakeClock()).execute(
            _command(date=date(2025, 1, 16))
        )


def test_create_transaction_rejects_unknown_type() -> None:
    with pytest.raises(InvalidTransactionInput, match="not a valid"):
        CreateTransaction(FakeTransactionRepository(), FakeClock()).execute(
            _command(transaction_type="transfer")
        )
