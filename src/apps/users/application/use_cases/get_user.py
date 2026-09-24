"""Single-user query use case."""

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.ports.repositories import UserRepository
from apps.users.domain.exceptions import UserNotFound
from apps.users.domain.value_objects import UserId


class GetUser:
    """Return a persisted user by identity."""

    def __init__(self, repository: UserRepository) -> None:
        self._repository = repository

    def execute(self, user_id: UserId) -> UserDetails:
        user = self._repository.get_by_id(user_id)
        if user is None:
            raise UserNotFound("User not found.")
        return user_details(user)
