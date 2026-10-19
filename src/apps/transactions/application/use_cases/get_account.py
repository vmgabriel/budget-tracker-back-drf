"""Single funding-account query use case."""

from uuid import UUID

from apps.transactions.application.dto import AccountDetails, account_details
from apps.transactions.application.ports.repositories import AccountRepository
from apps.transactions.application.scope import require_owned_account
from apps.transactions.domain.value_objects import AccountId


class GetAccount:
    """Return an account only when it belongs to the requesting user."""

    def __init__(self, repository: AccountRepository) -> None:
        self._repository = repository

    def execute(self, account_id: AccountId, user_id: UUID) -> AccountDetails:
        return account_details(
            require_owned_account(self._repository, account_id, user_id)
        )
