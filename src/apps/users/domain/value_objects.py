"""Value objects for the users domain."""

import re
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class PlanLevel(StrEnum):
    """Subscription plans available to a user."""

    FREE = "free"
    PRO = "pro"
    PREMIUM = "premium"

    @property
    def label(self) -> str:
        return self.value.capitalize()


PLAN_CHOICES: tuple[tuple[str, str], ...] = (
    ("free", "Free"),
    ("pro", "Pro"),
    ("premium", "Premium"),
)


@dataclass(frozen=True, slots=True)
class UserId:
    """Identity of a persisted user."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("UserId must contain a UUID.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Email:
    """A normalized email address."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if len(normalized) > 254 or not _EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class FullName:
    """A non-empty display name."""

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split())
        if not normalized:
            raise ValueError("Full name cannot be empty.")
        if len(normalized) > 150:
            raise ValueError("Full name cannot exceed 150 characters.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class PasswordHash:
    """An opaque one-way password hash; raw passwords never enter the domain."""

    value: str

    def __post_init__(self) -> None:
        if not self.value.strip():
            raise ValueError("Password hash cannot be empty.")
        if len(self.value) > 255:
            raise ValueError("Password hash cannot exceed 255 characters.")


@dataclass(frozen=True, slots=True)
class BanReason:
    """A non-empty, bounded explanation for a user ban."""

    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip()
        if not normalized:
            raise ValueError("Ban reason cannot be empty.")
        if len(normalized) > 500:
            raise ValueError("Ban reason cannot exceed 500 characters.")
        object.__setattr__(self, "value", normalized)
