"""User registration use case."""

from dataclasses import dataclass

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.ports.repositories import UserRepository
from apps.users.application.ports.security import PasswordHasher
from apps.users.domain.entities import User
from apps.users.domain.exceptions import EmailAlreadyExists
from apps.users.domain.value_objects import Email, FullName, PasswordHash
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    email: str
    password: str
    full_name: str


class CreateUser:
    """Register a user with a normalized email and a hashed password."""

    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._clock = clock

    def execute(self, command: CreateUserCommand) -> UserDetails:
        if not 8 <= len(command.password) <= 128:
            raise InvalidUserInput(
                "Password must contain between 8 and 128 characters."
            )
        try:
            email = Email(command.email)
            full_name = FullName(command.full_name)
        except ValueError as exc:
            raise InvalidUserInput(str(exc)) from exc

        if self._repository.get_by_email(email) is not None:
            raise EmailAlreadyExists("A user with this email already exists.")

        user = User.create(
            email=email,
            password_hash=PasswordHash(self._password_hasher.hash(command.password)),
            full_name=full_name,
            now=self._clock.now(),
        )
        return user_details(self._repository.add(user))
