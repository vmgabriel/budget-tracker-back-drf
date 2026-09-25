"""Security ports for the users application."""

from typing import Protocol


class PasswordHasher(Protocol):
    """Hashes and verifies passwords outside the domain model."""

    def hash(self, raw_password: str) -> str:
        """Return a one-way password hash."""
        raise NotImplementedError()

    def verify(self, raw_password: str, encoded_password: str) -> bool:
        """Return whether the raw password matches the encoded password."""
        raise NotImplementedError()
