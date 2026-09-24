"""Bounded transaction listing use case."""

from uuid import UUID

from apps.transactions.application.dto import TransactionPage, transaction_details
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.ports.repositories import TransactionRepository

MAX_PAGE = 10_000


class ListUserTransactions:
    """Return a validated page owned by the requesting user."""

    def __init__(self, repository: TransactionRepository) -> None:
        self._repository = repository

    def execute(
        self, user_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> TransactionPage:
        if not 1 <= page <= MAX_PAGE:
            raise InvalidTransactionInput(f"Page must be between 1 and {MAX_PAGE}.")
        if not 1 <= page_size <= 100:
            raise InvalidTransactionInput("Page size must be between 1 and 100.")
        transactions, total = self._repository.list_by_user(
            user_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return TransactionPage(
            items=tuple(transaction_details(item) for item in transactions),
            total=total,
        )
