"""Persistence ports for transaction and funding-account aggregates."""

from typing import Protocol
from uuid import UUID

from apps.transactions.domain.entities import Account, Transaction
from apps.transactions.domain.value_objects import AccountId, TransactionId


class TransactionRepository(Protocol):
    """Storage operations required by transaction use cases."""

    def add(self, transaction: Transaction) -> Transaction:
        """Persist a new transaction and return its stored representation."""
        raise NotImplementedError()

    def get_by_id_for_user(
        self, transaction_id: TransactionId, user_id: UUID
    ) -> Transaction | None:
        """Find a transaction only when it belongs to ``user_id``."""
        ...

    def update(self, transaction: Transaction) -> Transaction:
        """Persist changes made to an existing transaction."""
        raise NotImplementedError()

    def delete(self, transaction: Transaction) -> None:
        """Delete an existing transaction."""
        raise NotImplementedError()

    def list_by_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Transaction], int]:
        """Return one page of transactions and the owner's total count."""
        raise NotImplementedError()


class AccountRepository(Protocol):
    """Storage operations required by funding-account use cases."""

    def add(self, account: Account) -> Account:
        """Persist a new account and return its stored representation."""
        raise NotImplementedError()

    def get_by_id_for_user(
        self, account_id: AccountId, user_id: UUID
    ) -> Account | None:
        """Find an account only when it belongs to ``user_id``."""
        ...

    def list_active_by_user(self, user_id: UUID) -> list[Account]:
        """Return the owner's active accounts ordered by name."""
        raise NotImplementedError()
