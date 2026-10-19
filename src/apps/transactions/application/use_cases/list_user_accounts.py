"""Active funding-account listing use case."""

from uuid import UUID

from apps.transactions.application.dto import AccountDetails, account_details_list
from apps.transactions.application.ports.repositories import AccountRepository


class ListUserAccounts:
    """Return the active funding accounts owned by the requesting user."""

    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def execute(self, user_id: UUID) -> tuple[AccountDetails, ...]:
        return account_details_list(self._repository.list_active_by_user(user_id))
