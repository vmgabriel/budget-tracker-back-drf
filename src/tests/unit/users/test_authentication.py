"""Credential authentication application tests."""

import pytest

from apps.users.application.exceptions import AuthenticationFailed
from apps.users.application.use_cases import AuthenticateUser

from .fakes import FakePasswordHasher, FakeUserRepository, make_user

pytestmark = pytest.mark.unit


def test_authenticate_user_returns_active_user_without_creating_session() -> None:
    repository = FakeUserRepository()
    user = make_user(email="person@example.com", password="correct-password")
    assert user.id is not None
    repository.users[user.id] = user

    result = AuthenticateUser(repository, FakePasswordHasher()).execute(
        email="PERSON@example.com", password="correct-password"
    )

    assert result.id == user.id
    assert result.email == "person@example.com"


def test_authenticate_user_rejects_wrong_password() -> None:
    repository = FakeUserRepository()
    user = make_user(email="person@example.com", password="correct-password")
    assert user.id is not None
    repository.users[user.id] = user

    with pytest.raises(AuthenticationFailed):
        AuthenticateUser(repository, FakePasswordHasher()).execute(
            email="person@example.com", password="wrong-password"
        )


def test_authenticate_user_rejects_inactive_user() -> None:
    repository = FakeUserRepository()
    user = make_user(
        email="person@example.com",
        password="correct-password",
        is_active=False,
    )
    assert user.id is not None
    repository.users[user.id] = user

    with pytest.raises(AuthenticationFailed):
        AuthenticateUser(repository, FakePasswordHasher()).execute(
            email="person@example.com", password="correct-password"
        )
