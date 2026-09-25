"""Credential authentication use case."""

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.exceptions import AuthenticationFailed
from apps.users.application.ports.repositories import UserRepository
from apps.users.application.ports.security import PasswordHasher
from apps.users.domain.value_objects import Email


class AuthenticateUser:
    """Validate email/password credentials without creating server state."""

    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher

    def execute(self, *, email: str, password: str) -> UserDetails:
        try:
            normalized_email = Email(email)
        except ValueError as exc:
            raise AuthenticationFailed("Invalid email or password.") from exc

        user = self._repository.get_by_email(normalized_email)
        password_matches = user is not None and self._password_hasher.verify(
            password, user.password_hash.value
        )
        if user is None or not password_matches or not user.is_active:
            raise AuthenticationFailed("Invalid email or password.")

        return user_details(user)
