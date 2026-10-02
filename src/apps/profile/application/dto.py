"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import datetime

from apps.profile.domain.entities import Profile
from apps.profile.domain.value_objects import DateFormat, ProfileId


@dataclass(frozen=True, slots=True)
class ProfileDetails:
    """Profile data safe to expose through an HTTP interface."""

    id: ProfileId
    first_name: str
    last_name: str
    timezone: str
    language: str
    currency: str
    date_format: DateFormat
    avatar_url: str | None
    bio: str | None
    created_at: datetime
    updated_at: datetime


def profile_details(profile: Profile) -> ProfileDetails:
    """Convert a persisted profile aggregate into a safe result."""
    if profile.id is None:
        raise ValueError("A persisted profile must have an identity.")
    return ProfileDetails(
        id=profile.id,
        first_name=profile.full_name.first_name,
        last_name=profile.full_name.last_name,
        timezone=profile.timezone.value,
        language=profile.language.value,
        currency=profile.currency.value,
        date_format=profile.date_format,
        avatar_url=profile.avatar_url.value if profile.avatar_url else None,
        bio=profile.bio.value if profile.bio else None,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )
