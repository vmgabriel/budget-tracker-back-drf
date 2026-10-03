"""Ban user use case."""

from dataclasses import dataclass

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.ports.repositories import UserRepository
from apps.users.domain.exceptions import UserNotFound
from apps.users.domain.value_objects import BanReason, UserId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class BanUserCommand:
    user_id: UserId
    reason: str


class BanUser:
    """Ban a user, blocking them from protected API endpoints."""

    def __init__(self, repository: UserRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: BanUserCommand) -> UserDetails:
        user = self._repository.get_by_id(command.user_id)
        if user is None:
            raise UserNotFound("User not found.")
        try:
            reason = BanReason(command.reason)
        except ValueError as exc:
            raise InvalidUserInput(str(exc)) from exc
        user.ban(reason, now=self._clock.now())
        return user_details(self._repository.update(user))
