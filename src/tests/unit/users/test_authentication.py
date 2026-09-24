"""Authentication and session application tests."""

import pytest

from apps.users.application.exceptions import AuthenticationFailed
from apps.users.application.use_cases import AuthenticateUser, LogoutUser

from .fakes import (
    FakePasswordHasher,
    FakeSession,
    FakeUserRepository,
    make_user,
)

pytestmark = pytest.mark.unit


def test_authenticate_user_starts_session_for_active_user() -> None:
    repository = FakeUserRepository()
    user = make_user(email="person@example.com", password="correct-password")
    assert user.id is not None
    repository.users[user.id] = user
    session = FakeSession()

    result = AuthenticateUser(repository, FakePasswordHasher(), session).execute(
        email="PERSON@example.com", password="correct-password"
    )

    assert result.id == user.id
    assert session.logged_in_id == user.id


def test_authenticate_user_rejects_wrong_password() -> None:
    repository = FakeUserRepository()
    user = make_user(email="person@example.com", password="correct-password")
    assert user.id is not None
    repository.users[user.id] = user

    with pytest.raises(AuthenticationFailed):
        AuthenticateUser(repository, FakePasswordHasher(), FakeSession()).execute(
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
        AuthenticateUser(repository, FakePasswordHasher(), FakeSession()).execute(
            email="person@example.com", password="correct-password"
        )


def test_logout_user_delegates_to_session() -> None:
    session = FakeSession()

    LogoutUser(session).execute()

    assert session.logout_calls == 1
