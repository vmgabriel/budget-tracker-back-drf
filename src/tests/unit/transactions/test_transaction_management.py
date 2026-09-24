"""Transaction query, update, list, and delete use-case tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.use_cases import (
    DeleteTransaction,
    GetTransaction,
    ListUserTransactions,
    UpdateTransaction,
    UpdateTransactionCommand,
)
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)

from .fakes import FIXED_NOW, FakeClock, FakeTransactionRepository, make_transaction

pytestmark = pytest.mark.unit


def test_get_transaction_enforces_owner_scope() -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    result = GetTransaction(repository).execute(transaction_id, owner_id)

    assert result.id == transaction_id
    with pytest.raises(TransactionNotFound):
        GetTransaction(repository).execute(transaction_id, uuid4())


def test_update_transaction_applies_partial_changes() -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None
    clock_time = FIXED_NOW.replace(day=16)
    clock = FakeClock(now=clock_time)

    result = UpdateTransaction(repository, clock).execute(
        UpdateTransactionCommand(
            transaction_id=transaction_id,
            user_id=owner_id,
            amount=Decimal("99.95"),
            transaction_type=TransactionType.SAVINGS,
            category="  Emergency   Fund ",
            description="",
        )
    )

    assert result.amount == Decimal("99.95")
    assert result.transaction_type is TransactionType.SAVINGS
    assert result.category == "Emergency Fund"
    assert result.description is None
    assert result.updated_at == clock_time


@pytest.mark.parametrize("amount", [Decimal("1.001"), Decimal("10000000000.00")])
def test_update_transaction_rejects_amounts_outside_storage_precision(
    amount: Decimal,
) -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    with pytest.raises(InvalidTransactionInput):
        UpdateTransaction(repository, FakeClock()).execute(
            UpdateTransactionCommand(
                transaction_id=transaction_id,
                user_id=owner_id,
                amount=amount,
            )
        )

    assert transaction.amount.amount == Decimal("25.00")


def test_update_transaction_rejects_future_date_and_preserves_state() -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None
    original_category = transaction.category

    with pytest.raises(InvalidTransactionInput, match="future"):
        UpdateTransaction(repository, FakeClock()).execute(
            UpdateTransactionCommand(
                transaction_id=transaction_id,
                user_id=owner_id,
                date=date(2025, 1, 17),
            )
        )

    assert transaction.category is original_category


def test_update_transaction_requires_a_field() -> None:
    transaction = make_transaction()
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    with pytest.raises(InvalidTransactionInput, match="At least one"):
        UpdateTransaction(repository, FakeClock()).execute(
            UpdateTransactionCommand(
                transaction_id=transaction_id,
                user_id=transaction.user_id,
            )
        )


def test_update_transaction_hides_other_owners_records() -> None:
    transaction = make_transaction()
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    with pytest.raises(TransactionNotFound):
        UpdateTransaction(repository, FakeClock()).execute(
            UpdateTransactionCommand(
                transaction_id=transaction_id,
                user_id=uuid4(),
                amount=Decimal("10.00"),
            )
        )


def test_list_user_transactions_is_paginated_and_owner_scoped() -> None:
    owner_id = uuid4()
    repository = FakeTransactionRepository()
    repository.add(
        make_transaction(user_id=owner_id, transaction_date=date(2025, 1, 9))
    )
    repository.add(
        make_transaction(user_id=owner_id, transaction_date=date(2025, 1, 12))
    )
    repository.add(make_transaction(user_id=uuid4()))

    result = ListUserTransactions(repository).execute(owner_id, page=1, page_size=1)

    assert result.total == 2
    assert len(result.items) == 1
    assert result.items[0].date == date(2025, 1, 12)


def test_list_user_transactions_validates_pagination() -> None:
    use_case = ListUserTransactions(FakeTransactionRepository())
    owner_id = uuid4()

    with pytest.raises(InvalidTransactionInput):
        use_case.execute(owner_id, page=0)
    with pytest.raises(InvalidTransactionInput):
        use_case.execute(owner_id, page=10_001)
    with pytest.raises(InvalidTransactionInput):
        use_case.execute(owner_id, page_size=101)


def test_delete_transaction_enforces_owner_scope() -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    repository = FakeTransactionRepository()
    repository.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    with pytest.raises(TransactionNotFound):
        DeleteTransaction(repository).execute(transaction_id, uuid4())
    assert transaction_id in repository.transactions

    DeleteTransaction(repository).execute(transaction_id, owner_id)
    assert transaction_id not in repository.transactions


def test_fake_transaction_helper_builds_valid_domain_values() -> None:
    transaction = make_transaction(amount=Decimal("12.34"))

    assert isinstance(transaction.id, TransactionId)
    assert transaction.amount == Money(Decimal("12.34"))
    assert transaction.category == Category("Food")
    assert transaction.date == TransactionDate(date(2025, 1, 10))
