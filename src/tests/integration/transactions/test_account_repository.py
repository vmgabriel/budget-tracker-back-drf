"""Django ORM adapter tests for funding accounts and account-linked transactions."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError
from django.db import transaction as db_transaction

from apps.transactions.domain.entities import Account, Transaction
from apps.transactions.domain.value_objects import (
    AccountId,
    AccountType,
    Category,
    Money,
    TransactionDate,
    TransactionType,
)
from apps.transactions.infrastructure.persistence.models import (
    Account as AccountModel,
)
from apps.transactions.infrastructure.persistence.models import (
    Transaction as TransactionModel,
)
from apps.transactions.infrastructure.persistence.repositories import (
    DjangoAccountRepository,
    DjangoTransactionRepository,
)
from tests.factories import AccountFactory, TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _new_account(user: Any, name: str = "Main Card") -> Account:
    return Account.create(
        user_id=user.id,
        name=name,
        account_type=AccountType.CREDIT_CARD,
        now=datetime(2025, 1, 15, tzinfo=UTC),
    )


def _new_transaction(user: Any, account_id: AccountId | None = None) -> Transaction:
    return Transaction.create(
        user_id=user.id,
        amount=Money(Decimal("25.00")),
        transaction_type=TransactionType.EXPENSE,
        category=Category("Food"),
        date=TransactionDate(date(2025, 1, 10)),
        description="Lunch",
        now=datetime(2025, 1, 15, tzinfo=UTC),
        account_id=account_id,
    )


def test_account_repository_round_trips_and_scopes_lookup() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    repository = DjangoAccountRepository()

    saved = repository.add(_new_account(owner, name="  Main   Card "))

    assert saved.id is not None
    assert saved.user_id == owner.id
    assert saved.name == "Main Card"
    assert saved.account_type is AccountType.CREDIT_CARD
    assert saved.is_active is True

    loaded = repository.get_by_id_for_user(saved.id, owner.id)
    assert loaded is not None
    assert loaded.id == saved.id
    assert repository.get_by_id_for_user(saved.id, other_user.id) is None


def test_account_repository_lists_only_active_owned_accounts_by_name() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    AccountFactory(user=owner, name="Visa")
    AccountFactory(user=owner, name="Amex")
    AccountFactory(user=owner, name="Old card", is_active=False)
    AccountFactory(user=other_user, name="Someone else")
    repository = DjangoAccountRepository()

    accounts = repository.list_active_by_user(owner.id)

    assert [account.name for account in accounts] == ["Amex", "Visa"]


def test_database_constraint_rejects_unknown_account_type() -> None:
    with pytest.raises(IntegrityError), db_transaction.atomic():
        AccountFactory(account_type="credit")


@pytest.mark.parametrize("name", ["", "   "])
def test_database_constraint_rejects_blank_account_name(name: str) -> None:
    with pytest.raises(IntegrityError), db_transaction.atomic():
        AccountFactory(name=name)


def test_transaction_round_trips_its_account_and_flat_account_name() -> None:
    owner: Any = UserFactory()
    account: Any = AccountFactory(user=owner, name="Checking")
    repository = DjangoTransactionRepository()

    saved = repository.add(_new_transaction(owner, account_id=AccountId(account.id)))

    assert saved.account_id == AccountId(account.id)
    assert saved.account_name == "Checking"
    assert saved.id is not None

    loaded = repository.get_by_id_for_user(saved.id, owner.id)
    assert loaded is not None
    assert loaded.account_name == "Checking"

    page, total = repository.list_by_user(owner.id, offset=0, limit=10)
    assert total == 1
    assert page[0].account_id == AccountId(account.id)
    assert page[0].account_name == "Checking"


def test_repository_links_and_unlinks_an_account() -> None:
    owner: Any = UserFactory()
    account: Any = AccountFactory(user=owner)
    repository = DjangoTransactionRepository()
    saved = repository.add(_new_transaction(owner))
    assert saved.id is not None
    assert saved.account_id is None
    assert saved.account_name is None

    saved.assign_account(
        account_id=AccountId(account.id),
        now=datetime(2025, 1, 16, tzinfo=UTC),
    )
    linked = repository.update(saved)
    assert linked.account_id == AccountId(account.id)
    assert linked.account_name == account.name
    assert TransactionModel.objects.get(pk=saved.id.value).account_id == account.id

    saved.update(
        amount=saved.amount,
        transaction_type=saved.transaction_type,
        category=saved.category,
        date=saved.date,
        description=saved.description,
        account_id=None,
        now=datetime(2025, 1, 17, tzinfo=UTC),
    )
    unlinked = repository.update(saved)
    assert unlinked.account_id is None
    assert unlinked.account_name is None


def test_deleting_an_account_keeps_transactions_without_a_funding_source() -> None:
    owner: Any = UserFactory()
    account: Any = AccountFactory(user=owner)
    transaction: Any = TransactionFactory(user=owner, account=account)

    account.delete()

    refreshed = TransactionModel.objects.get(pk=transaction.pk)
    assert refreshed.account_id is None
    assert refreshed.user_id == owner.id
    assert AccountModel.objects.filter(pk=account.pk).exists() is False
