"""Transaction update use case."""

from dataclasses import dataclass
from datetime import date as Date
from decimal import Decimal
from uuid import UUID

from apps.transactions.application.dto import TransactionDetails, transaction_details
from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.ports.repositories import TransactionRepository
from apps.transactions.domain.exceptions import (
    FutureTransactionDate,
    TransactionNotFound,
)
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdateTransactionCommand:
    """Partial input accepted when updating a transaction.

    ``None`` leaves a field unchanged. An empty description clears the current
    description.
    """

    transaction_id: TransactionId
    user_id: UUID
    amount: Decimal | None = None
    transaction_type: TransactionType | None = None
    category: str | None = None
    date: Date | None = None
    description: str | None = None


class UpdateTransaction:
    """Apply partial changes to a transaction owned by the requesting user."""

    def __init__(self, repository: TransactionRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: UpdateTransactionCommand) -> TransactionDetails:
        if (
            command.amount is None
            and command.transaction_type is None
            and command.category is None
            and command.date is None
            and command.description is None
        ):
            raise InvalidTransactionInput("At least one transaction field is required.")

        transaction = self._repository.get_by_id_for_user(
            command.transaction_id, command.user_id
        )
        if transaction is None:
            raise TransactionNotFound("Transaction not found.")

        try:
            amount = (
                Money(command.amount)
                if command.amount is not None
                else transaction.amount
            )
            transaction_type = (
                TransactionType(command.transaction_type)
                if command.transaction_type is not None
                else transaction.transaction_type
            )
            category = (
                Category(command.category)
                if command.category is not None
                else transaction.category
            )
            transaction_date = (
                TransactionDate(command.date)
                if command.date is not None
                else transaction.date
            )
        except (TypeError, ValueError) as error:
            raise InvalidTransactionInput(str(error)) from error

        description = (
            command.description.strip() or None
            if command.description is not None
            else transaction.description
        )
        try:
            transaction.update(
                amount=amount,
                transaction_type=transaction_type,
                category=category,
                date=transaction_date,
                description=description,
                now=self._clock.now(),
            )
        except (FutureTransactionDate, TypeError, ValueError) as error:
            raise InvalidTransactionInput(str(error)) from error
        return transaction_details(self._repository.update(transaction))
