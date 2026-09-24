"""Bounded user listing use case."""

from apps.users.application.dto import UserPage, user_details
from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.ports.repositories import UserRepository

MAX_PAGE = 10_000


class ListUsers:
    """Return a validated page of users for administrative interfaces."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def execute(self, *, page: int = 1, page_size: int = 20) -> UserPage:
        if not 1 <= page <= MAX_PAGE:
            raise InvalidUserInput(f"Page must be between 1 and {MAX_PAGE}.")
        if not 1 <= page_size <= 100:
            raise InvalidUserInput("Page size must be between 1 and 100.")
        users, total = self._repository.list(
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return UserPage(
            items=tuple(user_details(user) for user in users),
            total=total,
        )
