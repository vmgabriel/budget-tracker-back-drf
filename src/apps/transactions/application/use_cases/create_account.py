"""Funding-account creation use case."""

from dataclasses import dataclass
from uuid import UUID

from apps.transactions.application.dto import AccountDetails, account_details
from apps.transactions.application.exceptions import InvalidAccountInput
from apps.transactions.application.ports.repositories import AccountRepository
from apps.transactions.domain.entities import Account
from apps.transactions.domain.exceptions import InvalidAccountType
from apps.transactions.domain.value_objects import AccountType
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CreateAccountCommand:
    """Input required to create a funding account."""

    user_id: UUID
    name: str
    account_type: AccountType


class CreateAccount:
    """Create and persist a funding account for an authenticated user."""

    def __init__(self, repository: AccountRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: CreateAccountCommand) -> AccountDetails:
        try:
            account_type = AccountType(str(command.account_type))
        except ValueError as error:
            raise InvalidAccountInput(
                f"Account type is invalid: {command.account_type}."
            ) from error
        try:
            account = Account.create(
                user_id=command.user_id,
                name=command.name,
                account_type=account_type,
                now=self._clock.now(),
            )
        except (InvalidAccountType, TypeError, ValueError) as error:
            raise InvalidAccountInput(str(error)) from error
        return account_details(self._repository.add(account))
