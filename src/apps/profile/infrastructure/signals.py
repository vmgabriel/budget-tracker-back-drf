"""Auto-provision a profile whenever a new user is created."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.infrastructure.persistence.models import ProfileModel

if TYPE_CHECKING:
    from apps.users.infrastructure.persistence.models import User

_NAME_PART_MAX_LENGTH = 100


@receiver(
    post_save,
    sender=settings.AUTH_USER_MODEL,
    dispatch_uid="profile_create_for_new_user",
)
def create_user_profile(
    sender: type[User],
    instance: User,
    created: bool,
    raw: bool,
    **kwargs: object,
) -> None:
    """Provision a profile for every newly created user.

    ``get_or_create`` keeps the handler idempotent and race-safe. Any failure
    propagates so the user insert rolls back with it, preserving the
    one-profile-per-user invariant.
    """
    del sender, kwargs
    if raw or not created:
        return
    first_name, last_name = _split_full_name(instance.full_name)
    ProfileModel.objects.get_or_create(
        user=instance,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "timezone": PROFILE_DEFAULTS.timezone.value,
            "language": PROFILE_DEFAULTS.language.value,
            "currency": PROFILE_DEFAULTS.currency.value,
            "date_format": PROFILE_DEFAULTS.date_format.value,
        },
    )


def _split_full_name(full_name: str) -> tuple[str, str]:
    """Split a display name into bounded first and last name parts."""
    parts = full_name.split()
    if not parts:
        return "", ""
    return (
        parts[0][:_NAME_PART_MAX_LENGTH],
        " ".join(parts[1:])[:_NAME_PART_MAX_LENGTH],
    )
