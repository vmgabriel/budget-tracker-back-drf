"""Persistence port for transaction aggregates."""

from typing import Protocol
from uuid import UUID

from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.value_objects import TransactionId


class TransactionRepository(Protocol):
    """Storage operations required by transaction use cases."""

    def add(self, transaction: Transaction) -> Transaction:
        """Persist a new transaction and return its stored representation."""
        raise NotImplementedError()

    def get_by_id_for_user(
        self, transaction_id: TransactionId, user_id: UUID
    ) -> Transaction | None:
        """Find a transaction only when it belongs to ``user_id``."""

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
