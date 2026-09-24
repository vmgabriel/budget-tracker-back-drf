"""Persistence port for the users context."""

from typing import Protocol

from apps.users.domain.entities import User
from apps.users.domain.value_objects import Email, UserId


class UserRepository(Protocol):
    """Storage operations required by user use cases."""

    def add(self, user: User) -> User:
        """Persist a new user and return its stored representation."""
        raise NotImplementedError()

    def get_by_email(self, email: Email) -> User | None:
        """Find a user by normalized email address."""
        ...

    def get_by_id(self, user_id: UserId) -> User | None:
        """Find a user by identity."""
        ...

    def update(self, user: User) -> User:
        """Persist changes made to an existing user."""
        raise NotImplementedError()

    def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        """Return a page of users and the total number of users."""
        raise NotImplementedError()
