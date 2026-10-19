"""Use case linking an existing transaction to a funding account."""

from dataclasses import dataclass
from uuid import UUID

from apps.transactions.application.dto import TransactionDetails, transaction_details
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.ports.repositories import (
    AccountRepository,
    TransactionRepository,
)
from apps.transactions.application.scope import require_owned_account
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import AccountId, TransactionId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdateTransactionAccountCommand:
    """Input required to link a transaction to a funding account."""

    transaction_id: TransactionId
    user_id: UUID
    account_id: AccountId


class UpdateTransactionAccount:
    """Attach one of the owner's accounts to one of the owner's transactions."""

    def __init__(
        self,
        repository: TransactionRepository,
        accounts: AccountRepository,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._accounts = accounts
        self._clock = clock

    def execute(self, command: UpdateTransactionAccountCommand) -> TransactionDetails:
        if not isinstance(command.account_id, AccountId):
            raise InvalidTransactionInput(
                "Transaction account must be identified by an AccountId."
            )
        transaction = self._repository.get_by_id_for_user(
            command.transaction_id, command.user_id
        )
        if transaction is None:
            raise TransactionNotFound("Transaction not found.")
        require_owned_account(self._accounts, command.account_id, command.user_id)
        try:
            transaction.assign_account(
                account_id=command.account_id,
                now=self._clock.now(),
            )
        except (TypeError, ValueError) as error:
            raise InvalidTransactionInput(str(error)) from error
        return transaction_details(self._repository.update(transaction))
