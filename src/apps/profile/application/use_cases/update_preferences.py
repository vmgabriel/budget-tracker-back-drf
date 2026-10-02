"""Profile regional-preferences update use case."""

from dataclasses import dataclass

from apps.profile.application.dto import ProfileDetails, profile_details
from apps.profile.application.exceptions import InvalidProfileInput
from apps.profile.application.ports.repositories import ProfileRepository
from apps.profile.domain.exceptions import ProfileDomainError, ProfileNotFound
from apps.profile.domain.value_objects import (
    Currency,
    DateFormat,
    Language,
    UserId,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdatePreferencesCommand:
    """Partial input accepted when updating regional preferences.

    ``None`` leaves a field unchanged.
    """

    user_id: UserId
    language: str | None = None
    currency: str | None = None
    date_format: str | None = None


class UpdatePreferences:
    """Apply partial changes to the requesting user's regional preferences."""

    def __init__(self, repository: ProfileRepository, clock: Clock) -> None:
        self._repository = repository
        self._clock = clock

    def execute(self, command: UpdatePreferencesCommand) -> ProfileDetails:
        if (
            command.language is None
            and command.currency is None
            and command.date_format is None
        ):
            raise InvalidProfileInput("At least one preference field is required.")

        profile = self._repository.get_by_user_id(command.user_id)
        if profile is None:
            raise ProfileNotFound("Profile not found.")

        try:
            language = (
                Language(command.language)
                if command.language is not None
                else profile.language
            )
            currency = (
                Currency(command.currency)
                if command.currency is not None
                else profile.currency
            )
            date_format = (
                DateFormat(command.date_format)
                if command.date_format is not None
                else profile.date_format
            )
        except (ProfileDomainError, TypeError, ValueError) as error:
            raise InvalidProfileInput(str(error)) from error

        try:
            profile.update_preferences(
                language=language,
                currency=currency,
                date_format=date_format,
                now=self._clock.now(),
            )
        except (TypeError, ValueError) as error:
            raise InvalidProfileInput(str(error)) from error
        return profile_details(self._repository.update(profile))
