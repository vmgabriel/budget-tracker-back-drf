"""Administrative plan and profile use-case tests."""

from uuid import uuid4

import pytest

from apps.users.application.use_cases import (
    AdminUpdateUser,
    AdminUpdateUserCommand,
    ChangeUserPlan,
    ChangeUserPlanCommand,
)
from apps.users.domain.exceptions import UserNotFound
from apps.users.domain.value_objects import PlanLevel, UserId

from .fakes import FakeClock, FakeUserRepository, make_user

pytestmark = pytest.mark.unit


def test_change_user_plan_persists_new_plan() -> None:
    repository = FakeUserRepository()
    user = make_user()
    assert user.id is not None
    repository.users[user.id] = user

    result = ChangeUserPlan(repository, FakeClock()).execute(
        ChangeUserPlanCommand(user_id=user.id, plan=PlanLevel.PREMIUM)
    )

    assert result.plan is PlanLevel.PREMIUM
    assert user.id is not None
    assert repository.users[user.id].plan is PlanLevel.PREMIUM


def test_change_user_plan_rejects_unknown_identity() -> None:
    with pytest.raises(UserNotFound):
        ChangeUserPlan(FakeUserRepository(), FakeClock()).execute(
            ChangeUserPlanCommand(
                user_id=UserId(uuid4()),
                plan=PlanLevel.PRO,
            )
        )


def test_admin_update_changes_profile_fields() -> None:
    repository = FakeUserRepository()
    user = make_user()
    assert user.id is not None
    repository.users[user.id] = user

    result = AdminUpdateUser(repository, FakeClock()).execute(
        AdminUpdateUserCommand(
            user_id=user.id,
            full_name="Updated Name",
            is_active=False,
        )
    )

    assert result.full_name == "Updated Name"
    assert result.is_active is False
    assert result.updated_at == user.updated_at
