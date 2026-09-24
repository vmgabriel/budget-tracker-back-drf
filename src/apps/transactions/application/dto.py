"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime
from decimal import Decimal

from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.value_objects import TransactionId, TransactionType


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


@dataclass(frozen=True, slots=True)
class TransactionPage:
    """A bounded page of transaction details."""

    items: tuple[TransactionDetails, ...]
    total: int


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
    )
