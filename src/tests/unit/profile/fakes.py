"""In-memory test doubles for profile application ports."""

from datetime import UTC, date, datetime
from uuid import uuid4

from apps.profile.domain.entities import Profile
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

FIXED_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


class FakeProfileRepository:
    """Store profile aggregates in memory for application tests."""

    def __init__(self) -> None:
        self.profiles: dict[UserId, Profile] = {}

    def get_by_user_id(self, user_id: UserId) -> Profile | None:
        return self.profiles.get(user_id)

    def save(self, profile: Profile) -> Profile:
        if profile.id is None:
            profile.id = ProfileId(uuid4())
        self.profiles[profile.user_id] = profile
        return profile

    def update(self, profile: Profile) -> Profile:
        if profile.id is None:
            raise ValueError("Cannot update an unidentified profile.")
        self.profiles[profile.user_id] = profile
        return profile


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


def make_profile(
    *,
    user_id: UserId | None = None,
    first_name: str = "Test",
    last_name: str = "User",
    timezone: str = "UTC",
    language: str = "es",
    currency: str = "USD",
    date_format: DateFormat = DateFormat.ISO,
    avatar_url: str | None = None,
    bio: str | None = None,
    now: datetime = FIXED_NOW,
) -> Profile:
    """Build a persisted profile for use-case tests."""
    profile = Profile.create(
        user_id=user_id or UserId(uuid4()),
        full_name=FullName(first_name, last_name),
        timezone=Timezone(timezone),
        language=Language(language),
        currency=Currency(currency),
        date_format=date_format,
        now=now,
        avatar_url=AvatarUrl(avatar_url) if avatar_url else None,
        bio=Bio(bio) if bio else None,
    )
    profile.id = ProfileId(uuid4())
    return profile
