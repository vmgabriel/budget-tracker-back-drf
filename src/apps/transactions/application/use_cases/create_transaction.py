"""Transaction creation use case."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from uuid import UUID

from apps.transactions.application.dto import TransactionDetails, transaction_details
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.ports.repositories import (
    AccountRepository,
    TransactionRepository,
)
from apps.transactions.application.scope import require_owned_account
from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.exceptions import FutureTransactionDate
from apps.transactions.domain.value_objects import (
    AccountId,
    Category,
    Money,
    TransactionDate,
    TransactionType,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CreateTransactionCommand:
    """Input required to create a transaction."""

    user_id: UUID
    amount: Decimal
    transaction_type: TransactionType
    category: str
    date: Date
    description: str | None = None
    account_id: AccountId | None = None


class CreateTransaction:
    """Create and persist a transaction for an authenticated user."""

    def __init__(
        self,
        repository: TransactionRepository,
        clock: Clock,
        accounts: AccountRepository,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._accounts = accounts

    def execute(self, command: CreateTransactionCommand) -> TransactionDetails:
        try:
            amount = Money(command.amount)
            transaction_type = TransactionType(command.transaction_type)
            category = Category(command.category)
            transaction_date = TransactionDate(command.date)
        except (TypeError, ValueError) as error:
            raise InvalidTransactionInput(str(error)) from error

        if command.account_id is not None:
            require_owned_account(self._accounts, command.account_id, command.user_id)

        description = (
            command.description.strip() or None
            if command.description is not None
            else None
        )
        try:
            transaction = Transaction.create(
                user_id=command.user_id,
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                date=transaction_date,
                description=description,
                now=self._clock.now(),
                account_id=command.account_id,
            )
        except (FutureTransactionDate, TypeError, ValueError) as error:
            raise InvalidTransactionInput(str(error)) from error
        return transaction_details(self._repository.add(transaction))
