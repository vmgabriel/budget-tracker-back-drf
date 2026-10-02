"""Profile provisioning shared by the user signal and backfill command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.infrastructure.persistence.models import ProfileModel

if TYPE_CHECKING:
    from apps.users.infrastructure.persistence.models import User

_NAME_PART_MAX_LENGTH = 100


def split_full_name(full_name: str) -> tuple[str, str]:
    """Split a display name into bounded first and last name parts."""
    parts = full_name.split()
    if not parts:
        return "", ""
    return (
        parts[0][:_NAME_PART_MAX_LENGTH],
        " ".join(parts[1:])[:_NAME_PART_MAX_LENGTH],
    )


def provision_profile(user: User) -> tuple[ProfileModel, bool]:
    """Provision a profile for ``user`` with the configured defaults.

    ``get_or_create`` keeps provisioning idempotent and race-safe, returning
    the existing row untouched when one is already present.
    """
    first_name, last_name = split_full_name(user.full_name)
    return ProfileModel.objects.get_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "timezone": PROFILE_DEFAULTS.timezone.value,
            "language": PROFILE_DEFAULTS.language.value,
            "currency": PROFILE_DEFAULTS.currency.value,
            "date_format": PROFILE_DEFAULTS.date_format.value,
        },
    )
