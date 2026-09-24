"""Django ORM adapter tests for users."""

from datetime import UTC, datetime

import pytest

from apps.users.domain.entities import User as UserEntity
from apps.users.domain.exceptions import EmailAlreadyExists
from apps.users.domain.value_objects import Email, FullName, PasswordHash, PlanLevel
from apps.users.infrastructure.persistence.models import User
from apps.users.infrastructure.persistence.repositories import DjangoUserRepository
from apps.users.infrastructure.security import DjangoPasswordHasher

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _new_user() -> UserEntity:
    return UserEntity.create(
        email=Email("repository@example.com"),
        password_hash=PasswordHash("encoded:repository-password"),
        full_name=FullName("Repository User"),
        now=datetime(2025, 1, 1, tzinfo=UTC),
    )


def test_repository_round_trips_and_updates_user() -> None:
    repository = DjangoUserRepository()
    user = _new_user()

    saved = repository.add(user)
    assert saved.id is not None
    loaded = repository.get_by_id(saved.id)
    assert loaded is not None
    assert loaded.email.value == "repository@example.com"
    assert loaded.full_name.value == "Repository User"
    assert loaded.password_hash.value == "encoded:repository-password"

    loaded.change_plan(PlanLevel.PRO, now=datetime(2025, 1, 2, tzinfo=UTC))
    loaded.update_profile(
        FullName("Updated Repository User"), now=datetime(2025, 1, 2, tzinfo=UTC)
    )
    updated = repository.update(loaded)

    assert updated.plan is PlanLevel.PRO
    assert updated.full_name.value == "Updated Repository User"
    assert User.objects.get(pk=saved.id.value).plan == PlanLevel.PRO.value


def test_repository_rejects_duplicate_email() -> None:
    repository = DjangoUserRepository()
    first = UserEntity.create(
        email=Email("duplicate@example.com"),
        password_hash=PasswordHash("encoded:one"),
        full_name=FullName("First User"),
        now=datetime(2025, 1, 1, tzinfo=UTC),
    )
    second = UserEntity.create(
        email=Email("DUPLICATE@example.com"),
        password_hash=PasswordHash("encoded:two"),
        full_name=FullName("Second User"),
        now=datetime(2025, 1, 1, tzinfo=UTC),
    )
    repository.add(first)
    with pytest.raises(EmailAlreadyExists):
        repository.add(second)


def test_custom_manager_creates_users_and_superusers() -> None:
    user = User.objects.create_user(
        email="manager@example.com",
        password="StrongPassword123!",
        full_name="Manager User",
    )
    administrator = User.objects.create_superuser(
        email="superuser@example.com",
        password="StrongPassword123!",
        full_name="Superuser",
    )

    assert user.check_password("StrongPassword123!")
    assert user.is_staff is False
    assert administrator.is_staff is True
    assert administrator.is_superuser is True


def test_django_password_hasher_hashes_and_verifies() -> None:
    hasher = DjangoPasswordHasher()

    encoded = hasher.hash("StrongPassword123!")

    assert encoded != "StrongPassword123!"
    assert hasher.verify("StrongPassword123!", encoded)
    assert not hasher.verify("wrong", encoded)
