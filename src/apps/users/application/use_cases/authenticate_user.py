"""User authentication use case."""

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.exceptions import AuthenticationFailed
from apps.users.application.ports.repositories import UserRepository
from apps.users.application.ports.security import PasswordHasher, UserSession
from apps.users.domain.value_objects import Email


class AuthenticateUser:
    """Authenticate credentials and start the opaque user session."""

    def __init__(
        self,
        repository: UserRepository,
        password_hasher: PasswordHasher,
        session: UserSession,
    ) -> None:
        self._repository = repository
        self._password_hasher = password_hasher
        self._session = session

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

        details = user_details(user)
        self._session.login(details.id)
        return details
