"""The profile aggregate and its business rules."""

from dataclasses import dataclass
from datetime import datetime

from apps.profile.domain.value_objects import (
    AvatarUrl,
    Bio,
    Currency,
    DateFormat,
    FullName,
    Language,
    ProfileId,
    Timezone,
    UserId,
)

_DEFAULT_TIMEZONE = Timezone("UTC")
_DEFAULT_LANGUAGE = Language("es")
_DEFAULT_CURRENCY = Currency("USD")


@dataclass(eq=False, slots=True)
class Profile:
    """Personal data and regional preferences owned by a single user."""

    user_id: UserId
    full_name: FullName
    timezone: Timezone
    language: Language
    currency: Currency
    date_format: DateFormat
    avatar_url: AvatarUrl | None
    bio: Bio | None
    created_at: datetime
    updated_at: datetime
    id: ProfileId | None = None

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        full_name: FullName,
        now: datetime,
        timezone: Timezone = _DEFAULT_TIMEZONE,
        language: Language = _DEFAULT_LANGUAGE,
        currency: Currency = _DEFAULT_CURRENCY,
        date_format: DateFormat = DateFormat.ISO,
        avatar_url: AvatarUrl | None = None,
        bio: Bio | None = None,
    ) -> "Profile":
        """Create a profile applying the default regional preferences."""
        if not isinstance(date_format, DateFormat):
            raise ValueError("Date format is invalid.")
        cls._require_aware(now)
        return cls(
            id=None,
            user_id=user_id,
            full_name=full_name,
            timezone=timezone,
            language=language,
            currency=currency,
            date_format=date_format,
            avatar_url=avatar_url,
            bio=bio,
            created_at=now,
            updated_at=now,
        )

    def update_details(
        self,
        *,
        full_name: FullName,
        timezone: Timezone,
        avatar_url: AvatarUrl | None,
        bio: Bio | None,
        now: datetime,
    ) -> None:
        """Apply a complete validated replacement of the personal details."""
        self._require_aware(now)
        self.full_name = full_name
        self.timezone = timezone
        self.avatar_url = avatar_url
        self.bio = bio
        self.updated_at = now

    def update_preferences(
        self,
        *,
        language: Language,
        currency: Currency,
        date_format: DateFormat,
        now: datetime,
    ) -> None:
        """Apply a complete validated replacement of the regional preferences."""
        if not isinstance(date_format, DateFormat):
            raise ValueError("Date format is invalid.")
        self._require_aware(now)
        self.language = language
        self.currency = currency
        self.date_format = date_format
        self.updated_at = now

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Profile timestamps must be timezone-aware.")
