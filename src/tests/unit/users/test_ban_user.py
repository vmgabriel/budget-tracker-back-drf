"""Domain ban/unban and BanUser use-case tests."""

from uuid import uuid4

import pytest

from apps.users.application.exceptions import InvalidUserInput
from apps.users.application.use_cases import (
    BanUser,
    BanUserCommand,
    UnbanUser,
    UnbanUserCommand,
)
from apps.users.domain.exceptions import (
    UserAlreadyBanned,
    UserNotBanned,
    UserNotFound,
)
from apps.users.domain.value_objects import BanReason, UserId

from .fakes import FIXED_NOW, FakeClock, FakeUserRepository, make_user

pytestmark = pytest.mark.unit


def test_ban_reason_rejects_empty() -> None:
    with pytest.raises(ValueError):
        BanReason("   ")


def test_ban_reason_rejects_over_max_length() -> None:
    with pytest.raises(ValueError):
        BanReason("x" * 501)


def test_ban_sets_state_and_reason() -> None:
    user = make_user()
    user.ban(BanReason("Fraudulent activity"), now=FIXED_NOW)
    assert user.is_banned is True
    assert user.ban_reason is not None
    assert user.ban_reason.value == "Fraudulent activity"


def test_ban_twice_raises() -> None:
    user = make_user()
    user.ban(BanReason("Fraudulent activity"), now=FIXED_NOW)
    with pytest.raises(UserAlreadyBanned):
        user.ban(BanReason("Again"), now=FIXED_NOW)


def test_unban_clears_state() -> None:
    user = make_user()
    user.ban(BanReason("Fraudulent activity"), now=FIXED_NOW)
    user.unban(now=FIXED_NOW)
    assert user.is_banned is False
    assert user.ban_reason is None


def test_unban_without_ban_raises() -> None:
    with pytest.raises(UserNotBanned):
        make_user().unban(now=FIXED_NOW)


def test_ban_user_use_case_persists_ban() -> None:
    repository = FakeUserRepository()
    user = make_user()
    assert user.id is not None
    repository.users[user.id] = user

    result = BanUser(repository, FakeClock()).execute(
        BanUserCommand(user_id=user.id, reason="Terms violation")
    )

    assert result.is_banned is True
    assert result.ban_reason == "Terms violation"
    assert repository.users[user.id].is_banned is True
    ban_reason = repository.users[user.id].ban_reason
    assert ban_reason is not None
    assert ban_reason.value == "Terms violation"


def test_ban_user_use_case_rejects_blank_reason() -> None:
    repository = FakeUserRepository()
    user = make_user()
    assert user.id is not None
    repository.users[user.id] = user

    with pytest.raises(InvalidUserInput):
        BanUser(repository, FakeClock()).execute(
            BanUserCommand(user_id=user.id, reason="   ")
        )


def test_ban_user_use_case_unknown_user() -> None:
    with pytest.raises(UserNotFound):
        BanUser(FakeUserRepository(), FakeClock()).execute(
            BanUserCommand(user_id=UserId(uuid4()), reason="Terms violation")
        )


def test_unban_user_use_case_clears_ban() -> None:
    repository = FakeUserRepository()
    user = make_user()
    assert user.id is not None
    repository.users[user.id] = user
    BanUser(repository, FakeClock()).execute(
        BanUserCommand(user_id=user.id, reason="Terms violation")
    )

    result = UnbanUser(repository, FakeClock()).execute(
        UnbanUserCommand(user_id=user.id)
    )

    assert result.is_banned is False
    assert result.ban_reason is None
