"""Auto-provision a profile whenever a new user is created."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.profile.infrastructure.provisioning import provision_profile

if TYPE_CHECKING:
    from apps.users.infrastructure.persistence.models import User


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

    Provisioning is idempotent. Any failure propagates so the user insert
    rolls back with it, preserving the one-profile-per-user invariant.
    """
    del sender, kwargs
    if raw or not created:
        return
    provision_profile(instance)
