"""The transaction aggregate and its business rules."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.transactions.domain.exceptions import FutureTransactionDate
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)


@dataclass(eq=False, slots=True)
class Transaction:
    """One user-owned financial transaction."""

    user_id: UUID
    amount: Money
    transaction_type: TransactionType
    category: Category
    date: TransactionDate
    description: str | None
    created_at: datetime
    updated_at: datetime
    id: TransactionId | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        amount: Money,
        transaction_type: TransactionType,
        category: Category,
        date: TransactionDate,
        description: str | None,
        now: datetime,
    ) -> "Transaction":
        """Create a transaction after validating aggregate invariants."""
        if not isinstance(user_id, UUID):
            raise TypeError("Transaction owner must be identified by a UUID.")
        if not isinstance(transaction_type, TransactionType):
            raise ValueError("Transaction type is invalid.")
        cls._validate_date(date, now)
        return cls(
            id=None,
            user_id=user_id,
            amount=amount,
            transaction_type=transaction_type,
            category=category,
            date=date,
            description=description,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        amount: Money,
        transaction_type: TransactionType,
        category: Category,
        date: TransactionDate,
        description: str | None,
        now: datetime,
    ) -> None:
        """Apply a complete validated replacement to the transaction."""
        if not isinstance(transaction_type, TransactionType):
            raise ValueError("Transaction type is invalid.")
        self._validate_date(date, now)
        self.amount = amount
        self.transaction_type = transaction_type
        self.category = category
        self.date = date
        self.description = description
        self.updated_at = now

    @classmethod
    def _validate_date(cls, transaction_date: TransactionDate, now: datetime) -> None:
        cls._require_aware(now)
        if transaction_date.value > now.date():
            raise FutureTransactionDate("Transaction date cannot be in the future.")

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Transaction timestamps must be timezone-aware.")
