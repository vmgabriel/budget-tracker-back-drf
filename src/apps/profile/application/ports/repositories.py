"""Persistence port for profile aggregates."""

from typing import Protocol

from apps.profile.domain.entities import Profile
from apps.profile.domain.value_objects import UserId


class ProfileRepository(Protocol):
    """Storage operations required by profile use cases."""

    def get_by_user_id(self, user_id: UserId) -> Profile | None:
        """Find the profile owned by ``user_id``."""
        raise NotImplementedError()

    def save(self, profile: Profile) -> Profile:
        """Persist a new profile and return its stored representation."""
        raise NotImplementedError()

    def update(self, profile: Profile) -> Profile:
        """Persist changes made to an existing profile."""
        raise NotImplementedError()
