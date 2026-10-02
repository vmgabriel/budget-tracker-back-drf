"""Signal tests for automatic profile provisioning."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.infrastructure.persistence.models import ProfileModel
from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

User = get_user_model()


def test_creating_a_user_provisions_a_profile_with_configured_defaults() -> None:
    user: Any = User.objects.create_user(
        email="provisioned@example.com",
        password="StrongPass123!",
        full_name="  Mary Jane   Watson ",
    )

    profile = ProfileModel.objects.get(user=user)
    assert profile.first_name == "Mary"
    assert profile.last_name == "Jane Watson"
    assert profile.timezone == PROFILE_DEFAULTS.timezone.value
    assert profile.language == PROFILE_DEFAULTS.language.value
    assert profile.currency == PROFILE_DEFAULTS.currency.value
    assert profile.date_format == PROFILE_DEFAULTS.date_format.value
    assert profile.avatar_url is None
    assert profile.bio is None
    assert user.profile.pk == profile.pk


def test_signal_splits_single_token_names_into_first_name_only() -> None:
    user: Any = UserFactory(full_name="Madonna")

    profile = ProfileModel.objects.get(user=user)
    assert profile.first_name == "Madonna"
    assert profile.last_name == ""


def test_signal_truncates_name_parts_beyond_model_limits() -> None:
    long_token = "x" * 150
    user: Any = UserFactory(full_name=long_token)

    profile = ProfileModel.objects.get(user=user)
    assert profile.first_name == "x" * 100
    assert profile.last_name == ""


def test_resaving_an_existing_user_does_not_touch_the_profile() -> None:
    user: Any = UserFactory(full_name="Original Name")
    profile = ProfileModel.objects.get(user=user)
    profile.bio = "Custom bio"
    profile.save(update_fields=("bio",))

    user.full_name = "Renamed User"
    user.save(update_fields=("full_name",))

    profile.refresh_from_db()
    assert profile.first_name == "Original"
    assert profile.bio == "Custom bio"
    assert ProfileModel.objects.filter(user=user).count() == 1


def test_replaying_the_created_signal_is_idempotent() -> None:
    user: Any = UserFactory()

    post_save.send(sender=User, instance=user, created=True, raw=False)

    assert ProfileModel.objects.filter(user=user).count() == 1


def test_deleting_a_user_cascades_to_the_profile() -> None:
    user: Any = UserFactory()
    user_id = user.id
    assert ProfileModel.objects.filter(user_id=user_id).exists()

    user.delete()

    assert not ProfileModel.objects.filter(user_id=user_id).exists()
