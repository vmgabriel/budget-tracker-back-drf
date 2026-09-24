"""Django ORM adapter tests for transactions."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError
from django.db import transaction as db_transaction

from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionType,
)
from apps.transactions.infrastructure.persistence.models import (
    Transaction as TransactionModel,
)
from apps.transactions.infrastructure.persistence.repositories import (
    DjangoTransactionRepository,
)
from tests.factories import TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _new_transaction(user: Any, amount: Decimal = Decimal("25.00")) -> Transaction:
    return Transaction.create(
        user_id=user.id,
        amount=Money(amount),
        transaction_type=TransactionType.EXPENSE,
        category=Category("Food"),
        date=TransactionDate(date(2025, 1, 10)),
        description="Lunch",
        now=datetime(2025, 1, 15, tzinfo=UTC),
    )


def test_repository_round_trips_and_scopes_transaction_lookup() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    repository = DjangoTransactionRepository()

    saved = repository.add(_new_transaction(owner))

    assert saved.id is not None
    assert saved.user_id == owner.id
    assert saved.amount.amount == Decimal("25.00")
    assert saved.transaction_type is TransactionType.EXPENSE
    assert saved.category.value == "Food"
    assert saved.date.value == date(2025, 1, 10)
    assert saved.description == "Lunch"

    loaded = repository.get_by_id_for_user(saved.id, owner.id)
    assert loaded is not None
    assert loaded.id == saved.id
    assert repository.get_by_id_for_user(saved.id, other_user.id) is None


@pytest.mark.parametrize("amount", [Decimal("0.01"), Decimal("9999999999.99")])
def test_repository_round_trips_supported_amount_boundaries(amount: Decimal) -> None:
    owner: Any = UserFactory()
    repository = DjangoTransactionRepository()

    saved = repository.add(_new_transaction(owner, amount=amount))

    assert saved.id is not None
    assert saved.amount.amount == amount
    model = TransactionModel.objects.get(pk=saved.id.value)
    assert model.amount == amount


def test_repository_updates_and_deletes_transaction() -> None:
    owner: Any = UserFactory()
    repository = DjangoTransactionRepository()
    saved = repository.add(_new_transaction(owner))
    assert saved.id is not None

    saved.update(
        amount=Money(Decimal("99.95")),
        transaction_type=TransactionType.INVESTMENT,
        category=Category("Index fund"),
        date=TransactionDate(date(2025, 1, 14)),
        description=None,
        now=datetime(2025, 1, 16, tzinfo=UTC),
    )
    updated = repository.update(saved)

    model = TransactionModel.objects.get(pk=saved.id.value)
    assert updated.amount.amount == Decimal("99.95")
    assert updated.transaction_type is TransactionType.INVESTMENT
    assert updated.description is None
    assert model.description == ""
    assert model.amount == Decimal("99.95")

    repository.delete(updated)
    assert not TransactionModel.objects.filter(pk=saved.id.value).exists()


def test_repository_lists_only_owner_records_in_stable_order() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    older: Any = TransactionFactory(user=owner, date=date(2025, 1, 9))
    newer: Any = TransactionFactory(user=owner, date=date(2025, 1, 12))
    TransactionFactory(user=other_user, date=date(2025, 1, 15))
    repository = DjangoTransactionRepository()

    page, total = repository.list_by_user(owner.id, offset=0, limit=1)

    assert total == 2
    assert len(page) == 1
    assert page[0].id is not None
    assert page[0].id.value == newer.id
    assert older.user_id == owner.id


def test_database_constraint_rejects_non_positive_amount() -> None:
    with pytest.raises(IntegrityError), db_transaction.atomic():
        TransactionFactory(amount=Decimal("0.00"))


def test_database_constraint_rejects_unknown_transaction_type() -> None:
    with pytest.raises(IntegrityError), db_transaction.atomic():
        TransactionFactory(transaction_type="transfer")


@pytest.mark.parametrize("category", ["", "   "])
def test_database_constraint_rejects_blank_category(category: str) -> None:
    with pytest.raises(IntegrityError), db_transaction.atomic():
        TransactionFactory(category=category)
