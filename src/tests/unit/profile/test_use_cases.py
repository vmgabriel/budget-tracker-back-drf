"""Profile query and update use-case tests."""

from datetime import datetime
from uuid import uuid4

import pytest

from apps.profile.application.exceptions import InvalidProfileInput
from apps.profile.application.use_cases import (
    GetProfile,
    GetProfileCommand,
    UpdatePreferences,
    UpdatePreferencesCommand,
    UpdateProfile,
    UpdateProfileCommand,
)
from apps.profile.domain.exceptions import ProfileNotFound
from apps.profile.domain.value_objects import DateFormat, UserId

from .fakes import FIXED_NOW, FakeClock, FakeProfileRepository, make_profile

pytestmark = pytest.mark.unit


def test_get_profile_returns_flattened_details() -> None:
    profile = make_profile(
        avatar_url="https://cdn.example.com/a.png",
        bio="Hola",
    )
    repository = FakeProfileRepository()
    repository.save(profile)

    result = GetProfile(repository).execute(GetProfileCommand(user_id=profile.user_id))

    assert result.id == profile.id
    assert result.first_name == "Test"
    assert result.last_name == "User"
    assert result.timezone == "UTC"
    assert result.language == "es"
    assert result.currency == "USD"
    assert result.date_format is DateFormat.ISO
    assert result.avatar_url == "https://cdn.example.com/a.png"
    assert result.bio == "Hola"
    assert result.created_at == FIXED_NOW


def test_get_profile_raises_when_user_has_no_profile() -> None:
    repository = FakeProfileRepository()

    with pytest.raises(ProfileNotFound):
        GetProfile(repository).execute(GetProfileCommand(user_id=UserId(uuid4())))


def test_update_profile_merges_partial_changes_and_uses_clock() -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)
    clock_time = datetime(2026, 1, 16, tzinfo=FIXED_NOW.tzinfo)
    clock = FakeClock(now=clock_time)

    result = UpdateProfile(repository, clock).execute(
        UpdateProfileCommand(
            user_id=profile.user_id,
            first_name="  Ana ",
            timezone="America/Bogota",
        )
    )

    assert result.first_name == "Ana"
    assert result.last_name == "User"
    assert result.timezone == "America/Bogota"
    assert result.updated_at == clock_time
    assert result.created_at == FIXED_NOW


def test_update_profile_sets_and_clears_optional_fields() -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)
    clock = FakeClock()

    populated = UpdateProfile(repository, clock).execute(
        UpdateProfileCommand(
            user_id=profile.user_id,
            avatar_url="https://cdn.example.com/a.png",
            bio="  Hello  ",
        )
    )
    assert populated.avatar_url == "https://cdn.example.com/a.png"
    assert populated.bio == "Hello"

    cleared = UpdateProfile(repository, clock).execute(
        UpdateProfileCommand(
            user_id=profile.user_id,
            avatar_url="   ",
            bio="",
        )
    )
    assert cleared.avatar_url is None
    assert cleared.bio is None
    assert cleared.first_name == "Test"


def test_update_profile_requires_at_least_one_field() -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)

    with pytest.raises(InvalidProfileInput, match="At least one"):
        UpdateProfile(repository, FakeClock()).execute(
            UpdateProfileCommand(user_id=profile.user_id)
        )


def test_update_profile_raises_when_user_has_no_profile() -> None:
    repository = FakeProfileRepository()

    with pytest.raises(ProfileNotFound):
        UpdateProfile(repository, FakeClock()).execute(
            UpdateProfileCommand(user_id=UserId(uuid4()), first_name="Ghost")
        )


@pytest.mark.parametrize(
    "command_kwargs",
    [
        {"timezone": "Fake/Zone"},
        {"avatar_url": "not-a-url"},
        {"bio": "x" * 501},
        {"first_name": " ", "last_name": "  "},
        {"first_name": "x" * 101},
    ],
)
def test_update_profile_translates_domain_failures_into_invalid_input(
    command_kwargs: dict[str, str],
) -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)
    original_name = profile.full_name

    with pytest.raises(InvalidProfileInput):
        UpdateProfile(repository, FakeClock()).execute(
            UpdateProfileCommand(user_id=profile.user_id, **command_kwargs)
        )

    assert profile.full_name is original_name
    assert repository.get_by_user_id(profile.user_id) is profile


def test_update_preferences_merges_and_normalizes_partial_changes() -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)
    clock_time = datetime(2026, 1, 16, tzinfo=FIXED_NOW.tzinfo)

    result = UpdatePreferences(repository, FakeClock(now=clock_time)).execute(
        UpdatePreferencesCommand(
            user_id=profile.user_id,
            language="PT",
            currency="cop",
        )
    )

    assert result.language == "pt"
    assert result.currency == "COP"
    assert result.date_format is DateFormat.ISO
    assert result.updated_at == clock_time

    result = UpdatePreferences(repository, FakeClock(now=clock_time)).execute(
        UpdatePreferencesCommand(
            user_id=profile.user_id,
            date_format="DD/MM/YYYY",
        )
    )
    assert result.date_format is DateFormat.DAY_FIRST
    assert result.language == "pt"


def test_update_preferences_requires_at_least_one_field() -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)

    with pytest.raises(InvalidProfileInput, match="At least one"):
        UpdatePreferences(repository, FakeClock()).execute(
            UpdatePreferencesCommand(user_id=profile.user_id)
        )


def test_update_preferences_raises_when_user_has_no_profile() -> None:
    repository = FakeProfileRepository()

    with pytest.raises(ProfileNotFound):
        UpdatePreferences(repository, FakeClock()).execute(
            UpdatePreferencesCommand(user_id=UserId(uuid4()), language="en")
        )


@pytest.mark.parametrize(
    "command_kwargs",
    [
        {"language": "xx"},
        {"currency": "XYZ"},
        {"date_format": "31-12-2026"},
    ],
)
def test_update_preferences_translates_domain_failures_into_invalid_input(
    command_kwargs: dict[str, str],
) -> None:
    profile = make_profile()
    repository = FakeProfileRepository()
    repository.save(profile)

    with pytest.raises(InvalidProfileInput):
        UpdatePreferences(repository, FakeClock()).execute(
            UpdatePreferencesCommand(user_id=profile.user_id, **command_kwargs)
        )

    assert profile.language.value == "es"
    assert profile.currency.value == "USD"
    assert profile.date_format is DateFormat.ISO


def test_fake_profile_helper_builds_valid_domain_values() -> None:
    profile = make_profile(timezone="America/Bogota")

    assert profile.id is not None
    assert profile.timezone.value == "America/Bogota"
    assert profile.full_name.display == "Test User"
