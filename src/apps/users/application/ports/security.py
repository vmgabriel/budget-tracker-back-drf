"""Security and session ports for authentication use cases."""

from typing import Protocol

from apps.users.domain.value_objects import UserId


class PasswordHasher(Protocol):
    """Hashes and verifies passwords outside the domain model."""

    def hash(self, raw_password: str) -> str:
        """Return a one-way password hash."""
        raise NotImplementedError()

    def verify(self, raw_password: str, encoded_password: str) -> bool:
        """Return whether the raw password matches the encoded password."""
        raise NotImplementedError()


class UserSession(Protocol):
    """Opaque session operations required by authentication use cases."""

    def login(self, user_id: UserId) -> None:
        """Start a session for a user identity."""
        ...

    def logout(self) -> None:
        """End the current user session."""
        ...
