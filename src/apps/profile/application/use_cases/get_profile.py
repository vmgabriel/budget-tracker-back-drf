"""Current profile query use case."""

from dataclasses import dataclass

from apps.profile.application.dto import ProfileDetails, profile_details
from apps.profile.application.ports.repositories import ProfileRepository
from apps.profile.domain.exceptions import ProfileNotFound
from apps.profile.domain.value_objects import UserId


@dataclass(frozen=True, slots=True)
class GetProfileCommand:
    """Input accepted when retrieving the requesting user's profile."""

    user_id: UserId


class GetProfile:
    """Return the profile owned by the requesting user."""

    def __init__(self, repository: ProfileRepository) -> None:
        self._repository = repository

    def execute(self, command: GetProfileCommand) -> ProfileDetails:
        profile = self._repository.get_by_user_id(command.user_id)
        if profile is None:
            raise ProfileNotFound("Profile not found.")
        return profile_details(profile)
