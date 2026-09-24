"""Transaction deletion use case."""

from uuid import UUID

from apps.transactions.application.ports.repositories import TransactionRepository
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import TransactionId


class DeleteTransaction:
    """Delete a transaction only when it belongs to the requesting user."""

    def __init__(self, repository: TransactionRepository) -> None:
        self._repository = repository

    def execute(self, transaction_id: TransactionId, user_id: UUID) -> None:
        transaction = self._repository.get_by_id_for_user(transaction_id, user_id)
        if transaction is None:
            raise TransactionNotFound("Transaction not found.")
        self._repository.delete(transaction)
