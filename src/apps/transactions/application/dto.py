"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from apps.transactions.domain.entities import Account, Transaction
from apps.transactions.domain.value_objects import (
    AccountId,
    AccountType,
    TransactionId,
    TransactionType,
)


@dataclass(frozen=True, slots=True)
class AccountDetails:
    """Funding-account data safe to expose through an HTTP interface."""

    id: AccountId
    name: str
    account_type: AccountType
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class TransactionDetails:
    """Transaction data safe to expose through an HTTP interface."""

    id: TransactionId
    amount: Decimal
    transaction_type: TransactionType
    category: str
    date: Date
    description: str | None
    created_at: datetime
    updated_at: datetime
    account_id: AccountId | None = None
    account_name: str | None = None


@dataclass(frozen=True, slots=True)
class TransactionPage:
    """A bounded page of transaction details."""

    items: tuple[TransactionDetails, ...]
    total: int


def account_details(account: Account) -> AccountDetails:
    """Convert a persisted account aggregate into a safe result."""
    if account.id is None:
        raise ValueError("A persisted account must have an identity.")
    return AccountDetails(
        id=account.id,
        name=account.name,
        account_type=account.account_type,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
    )


def account_details_list(accounts: list[Account]) -> tuple[AccountDetails, ...]:
    """Convert a collection of persisted accounts into safe results."""
    return tuple(account_details(account) for account in accounts)


def transaction_details(transaction: Transaction) -> TransactionDetails:
    """Convert a persisted transaction aggregate into a safe result."""
    if transaction.id is None:
        raise ValueError("A persisted transaction must have an identity.")
    return TransactionDetails(
        id=transaction.id,
        amount=transaction.amount.amount,
        transaction_type=transaction.transaction_type,
        category=transaction.category.value,
        date=transaction.date.value,
        description=transaction.description,
        created_at=transaction.created_at,
        updated_at=transaction.updated_at,
        account_id=transaction.account_id,
        account_name=transaction.account_name,
    )
