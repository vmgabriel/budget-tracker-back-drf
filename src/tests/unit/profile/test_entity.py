"""Profile aggregate business-rule tests."""

from datetime import datetime
from uuid import uuid4

import pytest

from apps.profile.domain.entities import Profile
from apps.profile.domain.value_objects import (
    AvatarUrl,
    Bio,
    Currency,
    DateFormat,
    FullName,
    Language,
    Timezone,
    UserId,
)

from .fakes import FIXED_NOW

pytestmark = pytest.mark.unit


def _new_profile(*, now: datetime = FIXED_NOW) -> Profile:
    return Profile.create(
        user_id=UserId(uuid4()),
        full_name=FullName("Test", "User"),
        timezone=Timezone("UTC"),
        language=Language("es"),
        currency=Currency("USD"),
        date_format=DateFormat.ISO,
        now=now,
    )


def test_profile_create_stamps_identity_window_and_defaults() -> None:
    profile = _new_profile()

    assert profile.id is None
    assert profile.created_at == FIXED_NOW
    assert profile.updated_at == FIXED_NOW
    assert profile.avatar_url is None
    assert profile.bio is None


def test_profile_create_requires_a_real_date_format() -> None:
    with pytest.raises(ValueError, match="Date format is invalid"):
        Profile.create(
            user_id=UserId(uuid4()),
            full_name=FullName("Test", "User"),
            timezone=Timezone("UTC"),
            language=Language("es"),
            currency=Currency("USD"),
            date_format="YYYY-MM-DD",  # type: ignore[arg-type]
            now=FIXED_NOW,
        )


def test_profile_update_details_replaces_fields_and_bumps_updated_at() -> None:
    profile = _new_profile()
    later = datetime(2026, 1, 16, tzinfo=FIXED_NOW.tzinfo)

    profile.update_details(
        full_name=FullName("Ana", "Maria"),
        timezone=Timezone("America/Bogota"),
        avatar_url=AvatarUrl("https://cdn.example.com/a.png"),
        bio=Bio("Hola"),
        now=later,
    )

    assert profile.full_name.display == "Ana Maria"
    assert profile.timezone.value == "America/Bogota"
    assert profile.avatar_url is not None
    assert profile.avatar_url.value == "https://cdn.example.com/a.png"
    assert profile.bio is not None
    assert profile.bio.value == "Hola"
    assert profile.created_at == FIXED_NOW
    assert profile.updated_at == later


def test_profile_update_details_can_clear_optional_fields() -> None:
    profile = _new_profile()
    profile.update_details(
        full_name=FullName("Ana", "Maria"),
        timezone=Timezone("UTC"),
        avatar_url=AvatarUrl("https://cdn.example.com/a.png"),
        bio=Bio("Hola"),
        now=FIXED_NOW,
    )

    profile.update_details(
        full_name=FullName("Ana", "Maria"),
        timezone=Timezone("UTC"),
        avatar_url=None,
        bio=None,
        now=FIXED_NOW,
    )

    assert profile.avatar_url is None
    assert profile.bio is None


def test_profile_update_preferences_replaces_fields_and_bumps_updated_at() -> None:
    profile = _new_profile()
    later = datetime(2026, 1, 16, tzinfo=FIXED_NOW.tzinfo)

    profile.update_preferences(
        language=Language("pt"),
        currency=Currency("COP"),
        date_format=DateFormat.DAY_FIRST,
        now=later,
    )

    assert profile.language.value == "pt"
    assert profile.currency.value == "COP"
    assert profile.date_format is DateFormat.DAY_FIRST
    assert profile.full_name.display == "Test User"
    assert profile.created_at == FIXED_NOW
    assert profile.updated_at == later


def test_profile_update_preferences_rejects_raw_date_format_strings() -> None:
    profile = _new_profile()

    with pytest.raises(ValueError, match="Date format is invalid"):
        profile.update_preferences(
            language=Language("pt"),
            currency=Currency("COP"),
            date_format="DD/MM/YYYY",  # type: ignore[arg-type]
            now=FIXED_NOW,
        )

    assert profile.language.value == "es"


def test_profile_requires_timezone_aware_clock_values() -> None:
    naive = datetime(2026, 1, 15, 12)

    with pytest.raises(ValueError, match="timezone-aware"):
        _new_profile(now=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        _new_profile().update_details(
            full_name=FullName("Test", "User"),
            timezone=Timezone("UTC"),
            avatar_url=None,
            bio=None,
            now=naive,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        _new_profile().update_preferences(
            language=Language("es"),
            currency=Currency("USD"),
            date_format=DateFormat.ISO,
            now=naive,
        )
