"""Subscription plan change use case."""

from dataclasses import dataclass

from apps.users.application.dto import UserDetails, user_details
from apps.users.application.ports.repositories import UserRepository
from apps.users.domain.exceptions import UserNotFound
from apps.users.domain.value_objects import PlanLevel, UserId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class ChangeUserPlanCommand:
    user_id: UserId
    plan: PlanLevel


class ChangeUserPlan:
    """Change the plan of an existing user."""

    def __init__(self, repository: UserRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: ChangeUserPlanCommand) -> UserDetails:
        user = self._repository.get_by_id(command.user_id)
        if user is None:
            raise UserNotFound("User not found.")
        user.change_plan(command.plan, now=self._clock.now())
        return user_details(self._repository.update(user))
