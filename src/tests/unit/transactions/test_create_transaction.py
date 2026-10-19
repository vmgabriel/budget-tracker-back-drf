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
from apps.transactions.domain.exceptions import AccountNotFound
from apps.transactions.domain.value_objects import AccountId, TransactionType

from .fakes import (
    FakeAccountRepository,
    FakeClock,
    FakeTransactionRepository,
    make_account,
)

pytestmark = pytest.mark.unit


def _use_case(
    repository: FakeTransactionRepository | None = None,
    clock: FakeClock | None = None,
    accounts: FakeAccountRepository | None = None,
) -> CreateTransaction:
    return CreateTransaction(
        repository or FakeTransactionRepository(),
        clock or FakeClock(),
        accounts or FakeAccountRepository(),
    )


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

    result = _use_case(repository, clock).execute(_command())

    assert result.amount == Decimal("25.00")
    assert result.category == "Food and Drink"
    assert result.description == "Lunch"
    assert result.account_id is None
    assert result.account_name is None
    assert result.created_at == clock.now()
    assert result.updated_at == clock.now()
    assert len(repository.transactions) == 1


def test_create_transaction_links_an_account_owned_by_the_same_user() -> None:
    owner_id = uuid4()
    account_id = AccountId(uuid4())
    accounts = FakeAccountRepository()
    accounts.add(make_account(account_id=account_id.value, user_id=owner_id))

    result = _use_case(accounts=accounts).execute(
        _command(user_id=owner_id, account_id=account_id)
    )

    assert result.account_id == account_id


def test_create_transaction_rejects_a_foreign_or_unknown_account() -> None:
    account_id = AccountId(uuid4())
    accounts = FakeAccountRepository()
    accounts.add(make_account(account_id=account_id.value))

    with pytest.raises(AccountNotFound):
        _use_case(accounts=accounts).execute(_command(account_id=account_id))


def test_create_transaction_rejects_non_positive_amount() -> None:
    with pytest.raises(InvalidTransactionInput, match="greater than zero"):
        _use_case().execute(_command(amount=Decimal("0.00")))


@pytest.mark.parametrize(
    "amount",
    [Decimal("1.001"), Decimal("10000000000.00")],
)
def test_create_transaction_rejects_amounts_outside_storage_precision(
    amount: Decimal,
) -> None:
    repository = FakeTransactionRepository()

    with pytest.raises(InvalidTransactionInput):
        _use_case(repository).execute(_command(amount=amount))

    assert not repository.transactions


def test_create_transaction_rejects_future_date_using_injected_clock() -> None:
    with pytest.raises(InvalidTransactionInput, match="future"):
        _use_case().execute(_command(date=date(2025, 1, 16)))


def test_create_transaction_rejects_unknown_type() -> None:
    with pytest.raises(InvalidTransactionInput, match="not a valid"):
        _use_case().execute(_command(transaction_type="transfer"))
