"""Profile personal-details update use case."""

from collections.abc import Callable
from dataclasses import dataclass

from apps.profile.application.dto import ProfileDetails, profile_details
from apps.profile.application.exceptions import InvalidProfileInput
from apps.profile.application.ports.repositories import ProfileRepository
from apps.profile.domain.exceptions import ProfileDomainError, ProfileNotFound
from apps.profile.domain.value_objects import (
    AvatarUrl,
    Bio,
    FullName,
    Timezone,
    UserId,
)
from shared.domain.ports.clock import Clock


def _merge_optional_value[V](
    raw: str | None, current: V | None, factory: Callable[[str], V]
) -> V | None:
    """Build an optional value object from partial input.

    ``None`` keeps the current value; a blank string clears it; anything else
    is wrapped and validated by ``factory``.
    """
    if raw is None:
        return current
    if not raw.strip():
        return None
    return factory(raw)


@dataclass(frozen=True, slots=True)
class UpdateProfileCommand:
    """Partial input accepted when updating personal details.

    ``None`` leaves a field unchanged. A blank ``avatar_url`` or ``bio``
    clears the current value.
    """

    user_id: UserId
    first_name: str | None = None
    last_name: str | None = None
    timezone: str | None = None
    avatar_url: str | None = None
    bio: str | None = None


class UpdateProfile:
    """Apply partial changes to the requesting user's personal details."""

    def __init__(self, repository: ProfileRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: UpdateProfileCommand) -> ProfileDetails:
        if (
            command.first_name is None
            and command.last_name is None
            and command.timezone is None
            and command.avatar_url is None
            and command.bio is None
        ):
            raise InvalidProfileInput("At least one profile field is required.")

        profile = self._repository.get_by_user_id(command.user_id)
        if profile is None:
            raise ProfileNotFound("Profile not found.")

        try:
            full_name = FullName(
                first_name=(
                    command.first_name
                    if command.first_name is not None
                    else profile.full_name.first_name
                ),
                last_name=(
                    command.last_name
                    if command.last_name is not None
                    else profile.full_name.last_name
                ),
            )
            timezone = (
                Timezone(command.timezone)
                if command.timezone is not None
                else profile.timezone
            )
            avatar_url = _merge_optional_value(
                command.avatar_url, profile.avatar_url, AvatarUrl
            )
            bio = _merge_optional_value(command.bio, profile.bio, Bio)
        except (ProfileDomainError, TypeError, ValueError) as error:
            raise InvalidProfileInput(str(error)) from error

        try:
            profile.update_details(
                full_name=full_name,
                timezone=timezone,
                avatar_url=avatar_url,
                bio=bio,
                now=self._clock.now(),
            )
        except (TypeError, ValueError) as error:
            raise InvalidProfileInput(str(error)) from error
        return profile_details(self._repository.update(profile))
