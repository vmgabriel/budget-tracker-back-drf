"""Backfill management command tests."""

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command

from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.infrastructure.persistence.models import ProfileModel
from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_backfill_provisions_profiles_only_for_users_missing_one() -> None:
    legacy: Any = UserFactory(full_name="Legacy User")
    covered: Any = UserFactory(full_name="Covered User")
    covered_profile = ProfileModel.objects.get(user=covered)
    ProfileModel.objects.filter(user=legacy).delete()

    output = StringIO()
    call_command("backfill_profiles", stdout=output)

    profile = ProfileModel.objects.get(user=legacy)
    assert profile.first_name == "Legacy"
    assert profile.last_name == "User"
    assert profile.timezone == PROFILE_DEFAULTS.timezone.value
    assert profile.language == PROFILE_DEFAULTS.language.value
    assert profile.currency == PROFILE_DEFAULTS.currency.value
    assert profile.date_format == PROFILE_DEFAULTS.date_format.value
    assert ProfileModel.objects.get(user=covered).pk == covered_profile.pk
    assert output.getvalue().strip() == "Backfilled 1 of 1 users missing a profile."


def test_backfill_is_idempotent_when_every_user_has_a_profile() -> None:
    user: Any = UserFactory()

    first = StringIO()
    call_command("backfill_profiles", stdout=first)
    second = StringIO()
    call_command("backfill_profiles", stdout=second)

    expected = "Backfilled 0 of 0 users missing a profile."
    assert first.getvalue().strip() == expected
    assert second.getvalue().strip() == expected
    assert ProfileModel.objects.filter(user=user).count() == 1
