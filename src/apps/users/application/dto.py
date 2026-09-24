"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import datetime

from apps.users.domain.entities import User
from apps.users.domain.value_objects import PlanLevel, UserId


@dataclass(frozen=True, slots=True)
class UserDetails:
    """User data that does not expose credential material."""

    id: UserId
    email: str
    full_name: str
    plan: PlanLevel
    is_active: bool
    is_staff: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class UserPage:
    """A bounded collection of user details."""

    items: tuple[UserDetails, ...]
    total: int


def user_details(user: User) -> UserDetails:
    """Convert a domain user into a safe application result."""
    if user.id is None:
        raise ValueError("A persisted user must have an identity.")
    return UserDetails(
        id=user.id,
        email=user.email.value,
        full_name=user.full_name.value,
        plan=user.plan,
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )
