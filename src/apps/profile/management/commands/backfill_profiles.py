"""Provision profiles for users that predate the profile module."""

from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand

from apps.profile.infrastructure.provisioning import provision_profile


class Command(BaseCommand):
    """Backfill missing profiles without requiring user re-registration."""

    help = "Create profiles with the configured defaults for users missing one."

    def handle(self, *args: Any, **options: Any) -> None:
        del args, options
        user_model = apps.get_model("users", "User")
        pending = user_model.objects.filter(profile__isnull=True).order_by("email")
        total = pending.count()
        created = 0
        for user in pending.iterator():
            _profile, was_created = provision_profile(user)
            created += int(was_created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled {created} of {total} users missing a profile."
            )
        )
