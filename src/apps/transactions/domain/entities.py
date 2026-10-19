"""The transaction and funding-account aggregates and their business rules."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from apps.transactions.domain.exceptions import (
    FutureTransactionDate,
    InvalidAccountType,
)
from apps.transactions.domain.value_objects import (
    AccountId,
    AccountType,
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)

MAX_ACCOUNT_NAME_LENGTH = 100


def _require_aware(now: datetime) -> None:
    """Fail fast when a clock value is not timezone-aware."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Timestamps must be timezone-aware.")


def _normalize_name(name: str) -> str:
    """Return a trimmed, whitespace-collapsed account name."""
    if not isinstance(name, str):
        raise TypeError("Account name must be a string.")
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Account name cannot be empty.")
    if len(normalized) > MAX_ACCOUNT_NAME_LENGTH:
        raise ValueError(
            f"Account name cannot exceed {MAX_ACCOUNT_NAME_LENGTH} characters."
        )
    return normalized


@dataclass(eq=False, slots=True)
class Account:
    """One user-owned funding source (card, cash, or bank account)."""

    user_id: UUID
    name: str
    account_type: AccountType
    is_active: bool
    created_at: datetime
    updated_at: datetime
    id: AccountId | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        name: str,
        account_type: AccountType,
        now: datetime,
    ) -> "Account":
        """Create an active account after validating aggregate invariants."""
        if not isinstance(user_id, UUID):
            raise TypeError("Account owner must be identified by a UUID.")
        if not isinstance(account_type, AccountType):
            raise InvalidAccountType("Account type is invalid.")
        _require_aware(now)
        return cls(
            id=None,
            user_id=user_id,
            name=_normalize_name(name),
            account_type=account_type,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def deactivate(self, *, now: datetime) -> None:
        """Stop offering the account as a funding source for new transactions."""
        _require_aware(now)
        self.is_active = False
        self.updated_at = now


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
    account_id: AccountId | None = None
    # Read-model metadata hydrated by the persistence adapter so the API can
    # expose a flat ``account_name`` without an extra query. Never persisted.
    account_name: str | None = None

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
        account_id: AccountId | None = None,
    ) -> "Transaction":
        """Create a transaction after validating aggregate invariants."""
        if not isinstance(user_id, UUID):
            raise TypeError("Transaction owner must be identified by a UUID.")
        if not isinstance(transaction_type, TransactionType):
            raise ValueError("Transaction type is invalid.")
        cls._validate_account(account_id)
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
            account_id=account_id,
        )

    def update(
        self,
        *,
        amount: Money,
        transaction_type: TransactionType,
        category: Category,
        date: TransactionDate,
        description: str | None,
        account_id: AccountId | None,
        now: datetime,
    ) -> None:
        """Apply a complete validated replacement to the transaction."""
        if not isinstance(transaction_type, TransactionType):
            raise ValueError("Transaction type is invalid.")
        self._validate_account(account_id)
        self._validate_date(date, now)
        self.amount = amount
        self.transaction_type = transaction_type
        self.category = category
        self.date = date
        self.description = description
        self.account_id = account_id
        self.account_name = None
        self.updated_at = now

    def assign_account(self, *, account_id: AccountId, now: datetime) -> None:
        """Link the transaction to a funding account owned by the same user."""
        self._validate_account(account_id)
        _require_aware(now)
        self.account_id = account_id
        self.account_name = None
        self.updated_at = now

    @classmethod
    def _validate_date(cls, transaction_date: TransactionDate, now: datetime) -> None:
        _require_aware(now)
        if transaction_date.value > now.date():
            raise FutureTransactionDate("Transaction date cannot be in the future.")

    @staticmethod
    def _validate_account(account_id: AccountId | None) -> None:
        if account_id is not None and not isinstance(account_id, AccountId):
            raise TypeError("Transaction account must be identified by an AccountId.")
