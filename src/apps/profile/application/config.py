"""Application-level configuration for the profile bounded context."""

from dataclasses import dataclass

from apps.profile.domain.value_objects import (
    Currency,
    DateFormat,
    Language,
    Timezone,
)


@dataclass(frozen=True, slots=True)
class ProfileDefaults:
    """Default regional preferences assigned to newly provisioned profiles.

    These are application policy, not domain invariants: the domain validates
    values, while this configuration chooses them. A deployment serving a
    different region could provision profiles with, for example, ``EUR`` and
    ``Europe/Madrid`` instead of ``USD`` and ``UTC``.
    """

    timezone: Timezone
    language: Language
    currency: Currency
    date_format: DateFormat


PROFILE_DEFAULTS = ProfileDefaults(
    timezone=Timezone("UTC"),
    language=Language("es"),
    currency=Currency("USD"),
    date_format=DateFormat.ISO,
)
