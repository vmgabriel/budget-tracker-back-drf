"""Composition of profile use cases and infrastructure adapters."""

from dataclasses import dataclass

from apps.profile.application.use_cases import (
    GetProfile,
    UpdatePreferences,
    UpdateProfile,
)
from apps.profile.infrastructure.persistence.repositories import (
    DjangoProfileRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class ProfileUseCases:
    """Profile use cases sharing one persistence adapter."""

    get: GetProfile
    update: UpdateProfile
    update_preferences: UpdatePreferences


def build_profile_use_cases() -> ProfileUseCases:
    """Build profile use cases with infrastructure dependencies."""
    repository = DjangoProfileRepository()
    clock = SystemClock()
    return ProfileUseCases(
        get=GetProfile(repository),
        update=UpdateProfile(repository, clock),
        update_preferences=UpdatePreferences(repository, clock),
    )
