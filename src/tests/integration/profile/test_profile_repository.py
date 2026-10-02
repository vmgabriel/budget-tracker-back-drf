"""Django ORM adapter tests for profiles."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from django.db import IntegrityError
from django.db import transaction as db_transaction

from apps.profile.domain.entities import Profile
from apps.profile.domain.exceptions import ProfileNotFound
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
from apps.profile.infrastructure.persistence.models import ProfileModel
from apps.profile.infrastructure.persistence.repositories import (
    DjangoProfileRepository,
)
from tests.factories import ProfileFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


def _new_profile(user: Any) -> Profile:
    return Profile.create(
        user_id=UserId(user.id),
        full_name=FullName("Saved", "Profile"),
        timezone=Timezone("America/Bogota"),
        language=Language("es"),
        currency=Currency("COP"),
        date_format=DateFormat.DAY_FIRST,
        avatar_url=AvatarUrl("https://cdn.example.com/a.png"),
        bio=Bio("Colombian user"),
        now=_NOW,
    )


def test_repository_get_by_user_id_maps_the_signal_provisioned_profile() -> None:
    owner: Any = UserFactory(full_name="Signal Owner")
    repository = DjangoProfileRepository()

    loaded = repository.get_by_user_id(UserId(owner.id))

    assert loaded is not None
    assert loaded.id is not None
    assert loaded.user_id == UserId(owner.id)
    assert loaded.full_name == FullName("Signal", "Owner")
    assert loaded.timezone.value == "UTC"
    assert loaded.language.value == "es"
    assert loaded.currency.value == "USD"
    assert loaded.date_format is DateFormat.ISO
    assert loaded.avatar_url is None
    assert loaded.bio is None
    assert loaded.created_at.tzinfo is not None


def test_repository_get_by_user_id_returns_none_for_unknown_users() -> None:
    repository = DjangoProfileRepository()

    assert repository.get_by_user_id(UserId(uuid4())) is None


def test_repository_save_persists_a_new_profile() -> None:
    owner: Any = UserFactory()
    ProfileModel.objects.filter(user=owner).delete()
    repository = DjangoProfileRepository()

    saved = repository.save(_new_profile(owner))

    assert saved.id is not None
    model = ProfileModel.objects.get(pk=saved.id.value)
    assert model.user_id == owner.id
    assert model.first_name == "Saved"
    assert model.last_name == "Profile"
    assert model.timezone == "America/Bogota"
    assert model.language == "es"
    assert model.currency == "COP"
    assert model.date_format == "DD/MM/YYYY"
    assert model.avatar_url == "https://cdn.example.com/a.png"
    assert model.bio == "Colombian user"

    reloaded = repository.get_by_user_id(UserId(owner.id))
    assert reloaded is not None
    assert reloaded.full_name.display == "Saved Profile"
    assert reloaded.avatar_url == AvatarUrl("https://cdn.example.com/a.png")
    assert reloaded.bio == Bio("Colombian user")


def test_repository_save_rejects_a_second_profile_for_the_same_user() -> None:
    owner: Any = UserFactory()
    repository = DjangoProfileRepository()

    with db_transaction.atomic(), pytest.raises(IntegrityError):
        repository.save(_new_profile(owner))


def test_repository_update_persists_only_changed_fields() -> None:
    profile_model: Any = ProfileFactory(bio="original", timezone="UTC")
    repository = DjangoProfileRepository()
    profile = repository.get_by_user_id(UserId(profile_model.user_id))
    assert profile is not None

    profile.update_details(
        full_name=FullName("Renamed", "Person"),
        timezone=Timezone("Europe/Madrid"),
        avatar_url=None,
        bio=None,
        now=datetime(2026, 1, 16, tzinfo=UTC),
    )
    profile.update_preferences(
        language=Language("pt"),
        currency=Currency("EUR"),
        date_format=DateFormat.MONTH_FIRST,
        now=datetime(2026, 1, 16, tzinfo=UTC),
    )
    updated = repository.update(profile)

    assert updated.id == profile.id
    model = ProfileModel.objects.get(pk=profile_model.pk)
    assert model.first_name == "Renamed"
    assert model.last_name == "Person"
    assert model.timezone == "Europe/Madrid"
    assert model.language == "pt"
    assert model.currency == "EUR"
    assert model.date_format == "MM/DD/YYYY"
    assert model.avatar_url is None
    assert model.bio is None


def test_repository_update_raises_for_unknown_profiles() -> None:
    owner: Any = UserFactory()
    repository = DjangoProfileRepository()
    profile = _new_profile(owner)
    profile.id = ProfileId(uuid4())

    with pytest.raises(ProfileNotFound):
        repository.update(profile)


def test_repository_update_rejects_unidentified_profiles() -> None:
    owner: Any = UserFactory()
    repository = DjangoProfileRepository()

    with pytest.raises(ValueError, match="identity"):
        repository.update(_new_profile(owner))


def test_model_constraints_reject_invalid_rows() -> None:
    owner: Any = UserFactory()
    model = ProfileModel.objects.get(user=owner)

    model.date_format = "31-12-2026"
    with db_transaction.atomic(), pytest.raises(IntegrityError):
        model.save(update_fields=("date_format",))

    model.refresh_from_db()
    model.first_name = ""
    model.last_name = "   "
    with db_transaction.atomic(), pytest.raises(IntegrityError):
        model.save(update_fields=("first_name", "last_name"))
