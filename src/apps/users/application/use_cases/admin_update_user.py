"""Administrative profile update use case."""

from dataclasses import dataclass

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.ports.repositories import UserRepository
from apps.users.domain.exceptions import EmailAlreadyExists, UserNotFound
from apps.users.domain.value_objects import Email, FullName, UserId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class AdminUpdateUserCommand:
    user_id: UserId
    email: str | None = None
    full_name: str | None = None
    is_active: bool | None = None


class AdminUpdateUser:
    """Allow an administrator to update safe profile fields."""

    def __init__(self, repository: UserRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: AdminUpdateUserCommand) -> UserDetails:
        if (
            command.email is None
            and command.full_name is None
            and command.is_active is None
        ):
            raise InvalidUserInput("At least one profile field must be provided.")
        user = self._repository.get_by_id(command.user_id)
        if user is None:
            raise UserNotFound("User not found.")

        now = self._clock.now()
        if command.email is not None:
            try:
                email = Email(command.email)
            except ValueError as exc:
                raise InvalidUserInput(str(exc)) from exc
            existing_user = self._repository.get_by_email(email)
            if existing_user is not None and existing_user.id != command.user_id:
                raise EmailAlreadyExists("A user with this email already exists.")
            user.change_email(email, now=now)
        if command.full_name is not None:
            try:
                full_name = FullName(command.full_name)
            except ValueError as exc:
                raise InvalidUserInput(str(exc)) from exc
            user.update_profile(full_name, now=now)
        if command.is_active is not None:
            user.change_active_state(command.is_active, now=now)
        return user_details(self._repository.update(user))
