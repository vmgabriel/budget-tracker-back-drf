"""Domain value-object and aggregate rules."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from apps.users.domain.entities import User
from apps.users.domain.value_objects import (
    Email,
    FullName,
    PasswordHash,
    PlanLevel,
    UserId,
)

pytestmark = pytest.mark.unit


def test_email_is_trimmed_and_normalized() -> None:
    assert Email("  Person@Example.COM ").value == "person@example.com"


@pytest.mark.parametrize("value", ["", "person", "person@example", "a b@example.com"])
def test_email_rejects_invalid_addresses(value: str) -> None:
    with pytest.raises(ValueError):
        Email(value)


def test_full_name_collapses_whitespace() -> None:
    assert FullName("  Ada   Lovelace ").value == "Ada Lovelace"


def test_user_starts_on_free_plan_and_can_change_plan() -> None:
    now = datetime(2025, 1, 1, tzinfo=UTC)
    user = User.create(
        email=Email("ada@example.com"),
        password_hash=PasswordHash("encoded:password"),
        full_name=FullName("Ada Lovelace"),
        now=now,
    )

    assert user.plan is PlanLevel.FREE
    assert user.is_active is True
    assert user.id is None

    user.change_plan(PlanLevel.PREMIUM, now=now)

    assert user.plan is PlanLevel.PREMIUM


def test_user_requires_timezone_aware_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        User.create(
            email=Email("ada@example.com"),
            password_hash=PasswordHash("encoded:password"),
            full_name=FullName("Ada Lovelace"),
            now=datetime(2025, 1, 1),
        )


def test_user_id_wraps_uuid() -> None:
    assert UserId(uuid4()).value.__class__.__name__ == "UUID"
