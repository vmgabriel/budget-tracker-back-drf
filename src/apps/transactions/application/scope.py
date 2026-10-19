"""Owner-scoping helpers shared by transaction use cases.

The helpers raise the matching ``*NotFound`` when a resource is missing *or*
owned by somebody else, so a foreign resource is indistinguishable from a
non-existent one at the HTTP layer.
"""

from uuid import UUID

from apps.transactions.application.ports.repositories import AccountRepository
from apps.transactions.domain.entities import Account
from apps.transactions.domain.exceptions import AccountNotFound
from apps.transactions.domain.value_objects import AccountId


def require_owned_account(
    accounts: AccountRepository, account_id: AccountId, owner_id: UUID
) -> Account:
    """Return the account only when it exists and belongs to ``owner_id``."""
    account = accounts.get_by_id_for_user(account_id, owner_id)
    if account is None:
        raise AccountNotFound("Account not found.")
    return account
