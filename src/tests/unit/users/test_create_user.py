"""CreateUser application tests using in-memory ports."""

import pytest

from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.use_cases import CreateUser, CreateUserCommand
from apps.users.domain.exceptions import EmailAlreadyExists
from apps.users.domain.value_objects import Email, PlanLevel

from .fakes import FakeClock, FakePasswordHasher, FakeUserRepository

pytestmark = pytest.mark.unit


def test_create_user_normalizes_input_hashes_password_and_defaults_to_free() -> None:
    repository = FakeUserRepository()
    hasher = FakePasswordHasher()

    result = CreateUser(repository, hasher, FakeClock()).execute(
        CreateUserCommand(
            email="  Person@Example.com ",
            password="strong-password",
            full_name="  Person   Example ",
        )
    )

    assert result.email == "person@example.com"
    assert result.full_name == "Person Example"
    assert result.plan is PlanLevel.FREE
    assert hasher.hashed_passwords == ["strong-password"]
    assert next(iter(repository.users.values())).password_hash.value == (
        "encoded:strong-password"
    )


def test_create_user_rejects_duplicate_email_before_hashing() -> None:
    repository = FakeUserRepository()
    hasher = FakePasswordHasher()
    CreateUser(repository, hasher, FakeClock()).execute(
        CreateUserCommand(
            email="person@example.com",
            password="strong-password",
            full_name="Person Example",
        )
    )

    with pytest.raises(EmailAlreadyExists):
        CreateUser(repository, hasher, FakeClock()).execute(
            CreateUserCommand(
                email="PERSON@example.com",
                password="strong-password",
                full_name="Other Name",
            )
        )

    assert hasher.hashed_passwords == ["strong-password"]


def test_create_user_rejects_short_password() -> None:
    with pytest.raises(InvalidUserInput):
        CreateUser(FakeUserRepository(), FakePasswordHasher(), FakeClock()).execute(
            CreateUserCommand(
                email=Email("person@example.com").value,
                password="short",
                full_name="Person Example",
            )
        )
