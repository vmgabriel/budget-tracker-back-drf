"""Funding-account use-case tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.transactions.application.exceptions import (
    InvalidAccountInput,
    InvalidTransactionInput,
)
from apps.transactions.application.use_cases import (
    CreateAccount,
    CreateAccountCommand,
    GetAccount,
    ListUserAccounts,
    UpdateTransactionAccount,
    UpdateTransactionAccountCommand,
)
from apps.transactions.domain.exceptions import (
    AccountNotFound,
    TransactionNotFound,
)
from apps.transactions.domain.value_objects import AccountType

from .fakes import (
    FIXED_NOW,
    FakeAccountRepository,
    FakeClock,
    FakeTransactionRepository,
    make_account,
    make_transaction,
)

pytestmark = pytest.mark.unit


def _command(**overrides: object) -> CreateAccountCommand:
    values: dict[str, object] = {
        "user_id": uuid4(),
        "name": "  Main   Card ",
        "account_type": AccountType.CREDIT_CARD,
    }
    values.update(overrides)
    return CreateAccountCommand(**values)  # type: ignore[arg-type]


def test_create_account_normalizes_and_persists_an_active_account() -> None:
    repository = FakeAccountRepository()
    clock = FakeClock()

    result = CreateAccount(repository, clock).execute(_command())

    assert result.name == "Main Card"
    assert result.account_type is AccountType.CREDIT_CARD
    assert result.is_active is True
    assert result.created_at == clock.now()
    assert result.updated_at == clock.now()
    assert len(repository.accounts) == 1


@pytest.mark.parametrize(
    "account_type",
    ["credit", "CREDIT_CARD", "checking"],
)
def test_create_account_rejects_unknown_types(account_type: str) -> None:
    repository = FakeAccountRepository()

    with pytest.raises(InvalidAccountInput, match="Account type is invalid"):
        CreateAccount(repository, FakeClock()).execute(
            _command(account_type=account_type)
        )

    assert not repository.accounts


@pytest.mark.parametrize("name", ["", "   ", "x" * 101])
def test_create_account_rejects_blank_or_oversized_names(name: str) -> None:
    repository = FakeAccountRepository()

    with pytest.raises(InvalidAccountInput):
        CreateAccount(repository, FakeClock()).execute(_command(name=name))

    assert not repository.accounts


def test_list_user_accounts_returns_only_active_owned_accounts_by_name() -> None:
    owner_id = uuid4()
    repository = FakeAccountRepository()
    repository.add(make_account(user_id=owner_id, name="Visa"))
    repository.add(make_account(user_id=owner_id, name="Amex"))
    repository.add(make_account(user_id=owner_id, name="Old card", is_active=False))
    repository.add(make_account(name="Someone else"))

    result = ListUserAccounts(repository).execute(owner_id)

    assert [account.name for account in result] == ["Amex", "Visa"]
    assert all(account.is_active for account in result)


def test_get_account_enforces_owner_scope() -> None:
    owner_id = uuid4()
    account = make_account(user_id=owner_id)
    repository = FakeAccountRepository()
    repository.add(account)
    account_id = account.id
    assert account_id is not None

    result = GetAccount(repository).execute(account_id, owner_id)

    assert result.id == account_id
    with pytest.raises(AccountNotFound):
        GetAccount(repository).execute(account_id, uuid4())


def test_update_transaction_account_links_and_rehydrates_the_name() -> None:
    owner_id = uuid4()
    account = make_account(user_id=owner_id, name="Checking")
    accounts = FakeAccountRepository()
    accounts.add(account)
    account_id = account.id
    assert account_id is not None
    transaction = make_transaction(user_id=owner_id)
    transactions = FakeTransactionRepository()
    transactions.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None
    clock_time = FIXED_NOW.replace(day=16)

    result = UpdateTransactionAccount(
        transactions,
        accounts,
        FakeClock(now=clock_time),
    ).execute(
        UpdateTransactionAccountCommand(
            transaction_id=transaction_id,
            user_id=owner_id,
            account_id=account_id,
        )
    )

    assert result.account_id == account_id
    assert result.updated_at == clock_time
    assert result.amount == Decimal("25.00")
    assert result.date == date(2025, 1, 10)


def test_update_transaction_account_hides_other_owners_resources() -> None:
    owner_id = uuid4()
    foreign_account = make_account(name="Not mine")
    accounts = FakeAccountRepository()
    accounts.add(foreign_account)
    foreign_account_id = foreign_account.id
    assert foreign_account_id is not None
    transaction = make_transaction(user_id=owner_id)
    transactions = FakeTransactionRepository()
    transactions.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None
    use_case = UpdateTransactionAccount(transactions, accounts, FakeClock())

    with pytest.raises(AccountNotFound):
        use_case.execute(
            UpdateTransactionAccountCommand(
                transaction_id=transaction_id,
                user_id=owner_id,
                account_id=foreign_account_id,
            )
        )

    with pytest.raises(TransactionNotFound):
        use_case.execute(
            UpdateTransactionAccountCommand(
                transaction_id=transaction_id,
                user_id=uuid4(),
                account_id=foreign_account_id,
            )
        )


def test_update_transaction_account_requires_an_account_identity() -> None:
    owner_id = uuid4()
    transaction = make_transaction(user_id=owner_id)
    transactions = FakeTransactionRepository()
    transactions.add(transaction)
    transaction_id = transaction.id
    assert transaction_id is not None

    with pytest.raises(InvalidTransactionInput, match="AccountId"):
        UpdateTransactionAccount(
            transactions,
            FakeAccountRepository(),
            FakeClock(),
        ).execute(
            UpdateTransactionAccountCommand(
                transaction_id=transaction_id,
                user_id=owner_id,
                account_id=uuid4(),  # type: ignore[arg-type]
            )
        )
