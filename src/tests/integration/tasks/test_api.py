"""Owner-scoped tasks HTTP interface tests using JWT authentication."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.tasks.infrastructure.persistence.models import (
    DailyPlanModel,
    GoalModel,
    TaskModel,
)
from tests.factories import (
    DailyPlanFactory,
    GoalFactory,
    TaskFactory,
    UserFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

TODAY = date.today()


def _client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def _task_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Water the plants",
        "description": "Every three days",
        "importance": "medium",
        "estimated_hours": "1.50",
    }
    payload.update(overrides)
    return payload


def _goal_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"name": "Spring cleaning", "description": "Deep clean"}
    payload.update(overrides)
    return payload


def _create_task(client: APIClient, **overrides: Any) -> Any:
    response = client.post(
        reverse("api_v1:tasks:task-list"), _task_payload(**overrides), format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def _create_goal(client: APIClient, **overrides: Any) -> Any:
    response = client.post(
        reverse("api_v1:tasks:goal-list"), _goal_payload(**overrides), format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


def _open_plan(client: APIClient, day: date | None = None) -> Any:
    response = client.post(
        reverse("api_v1:tasks:dailyplan-list"),
        {"date": (day or TODAY).isoformat()},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.json()


# --- routing and authentication -------------------------------------------


def test_task_routes_live_at_the_api_root() -> None:
    sample: Any = GoalFactory()
    task_id = sample.id

    assert reverse("api_v1:tasks:task-list") == "/api/v1/tasks/tasks/"
    assert (
        reverse("api_v1:tasks:task-detail", kwargs={"pk": task_id})
        == f"/api/v1/tasks/tasks/{task_id}/"
    )
    assert (
        reverse("api_v1:tasks:task-mark-done", kwargs={"pk": task_id})
        == f"/api/v1/tasks/tasks/{task_id}/mark-done/"
    )
    assert reverse("api_v1:tasks:goal-list") == "/api/v1/tasks/goals/"
    assert reverse("api_v1:tasks:dailyplan-list") == "/api/v1/tasks/daily-plans/"


def test_task_endpoints_require_authentication() -> None:
    client = APIClient()

    assert (
        client.get(reverse("api_v1:tasks:task-list")).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.post(
            reverse("api_v1:tasks:task-list"), _task_payload(), format="json"
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


# --- task CRUD and owner scoping ------------------------------------------


def test_task_crud_round_trip(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _client(owner, jwt_token_factory)

    created = _create_task(client, due_date="2026-02-01")

    assert created["name"] == "Water the plants"
    assert created["importance"] == "medium"
    assert created["status"] == "todo"
    assert created["estimated_hours"] == "1.50"
    assert created["goal_id"] is None
    assert created["is_overwhelmed"] is False
    assert created["is_checked_by_llm"] is False
    assert created["llm_evaluation_failed"] is False

    detail_url = reverse("api_v1:tasks:task-detail", kwargs={"pk": created["id"]})
    assert client.get(detail_url).json()["id"] == created["id"]

    updated = client.patch(detail_url, {"name": "Water the ferns"}, format="json")
    assert updated.status_code == status.HTTP_200_OK
    assert updated.json()["name"] == "Water the ferns"
    assert updated.json()["due_date"] == "2026-02-01"

    assert client.delete(detail_url).status_code == status.HTTP_204_NO_CONTENT
    assert client.get(detail_url).status_code == status.HTTP_404_NOT_FOUND


def test_task_creation_validates_input(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    url = reverse("api_v1:tasks:task-list")

    blank = client.post(url, _task_payload(name="   "), format="json")
    unknown_priority = client.post(
        url, _task_payload(importance="urgent"), format="json"
    )
    negative_hours = client.post(
        url, _task_payload(estimated_hours="-1"), format="json"
    )
    bad_date = client.post(url, _task_payload(due_date="31-02-2026"), format="json")

    for response in (blank, unknown_priority, negative_hours, bad_date):
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert TaskModel.objects.count() == 0


def test_overwhelmed_flag_follows_the_configured_threshold(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    assert _create_task(client, estimated_hours="4.00")["is_overwhelmed"] is False
    assert _create_task(client, estimated_hours="4.01")["is_overwhelmed"] is True


def test_patch_keeps_absent_fields_and_clears_explicit_nulls(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = _create_task(client, due_date="2026-02-01")
    url = reverse("api_v1:tasks:task-detail", kwargs={"pk": created["id"]})

    untouched = client.patch(url, {"importance": "high"}, format="json")

    assert untouched.json()["due_date"] == "2026-02-01"
    assert untouched.json()["importance"] == "high"
    assert TaskModel.objects.get(pk=created["id"]).due_date == date(2026, 2, 1)

    cleared = client.patch(url, {"due_date": None}, format="json")

    assert cleared.json()["due_date"] is None
    assert TaskModel.objects.get(pk=created["id"]).due_date is None


def test_patch_without_any_field_is_rejected(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = _create_task(client)

    response = client.patch(
        reverse("api_v1:tasks:task-detail", kwargs={"pk": created["id"]}),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_editing_a_task_clears_the_llm_check_flag(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = _create_task(client)
    url = reverse("api_v1:tasks:task-detail", kwargs={"pk": created["id"]})
    TaskModel.objects.filter(pk=created["id"]).update(is_checked_by_llm=True)

    cosmetic = client.patch(url, {"estimated_hours": "2.00"}, format="json")
    assert cosmetic.json()["is_checked_by_llm"] is True

    substantive = client.patch(url, {"name": "Repaint the fence"}, format="json")
    assert substantive.json()["is_checked_by_llm"] is False


def test_foreign_tasks_are_invisible(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    stranger: Any = UserFactory()
    foreign: Any = TaskFactory(user=stranger)
    owner_client = _client(owner, jwt_token_factory)
    url = reverse("api_v1:tasks:task-detail", kwargs={"pk": foreign.id})

    assert owner_client.get(url).status_code == status.HTTP_404_NOT_FOUND
    assert owner_client.delete(url).status_code == status.HTTP_404_NOT_FOUND
    assert (
        owner_client.patch(url, {"name": "Mine now"}, format="json").status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        owner_client.post(
            reverse("api_v1:tasks:task-mark-done", kwargs={"pk": foreign.id})
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert owner_client.get(reverse("api_v1:tasks:task-list")).json() == []
    assert TaskModel.objects.get(pk=foreign.id).name == foreign.name


def test_task_list_filters_by_status_and_goal(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _client(owner, jwt_token_factory)
    goal = _create_goal(client)
    first = _create_task(client, name="First")
    second = _create_task(client, name="Second")
    list_url = reverse("api_v1:tasks:task-list")

    client.post(
        reverse("api_v1:tasks:goal-link-task", kwargs={"pk": goal["id"]}),
        {"task_id": second["id"]},
        format="json",
    )
    client.post(reverse("api_v1:tasks:task-mark-done", kwargs={"pk": first["id"]}))

    assert {item["name"] for item in client.get(list_url).json()} == {
        "First",
        "Second",
    }
    assert [
        item["name"] for item in client.get(list_url, {"status": "done"}).json()
    ] == ["First"]
    assert [
        item["name"] for item in client.get(list_url, {"goal_id": goal["id"]}).json()
    ] == ["Second"]
    assert client.get(list_url, {"status": "archived"}).status_code == (
        status.HTTP_400_BAD_REQUEST
    )


# --- task actions ----------------------------------------------------------


def test_task_actions_move_status_and_importance(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = _create_task(client, importance="low")
    pk = created["id"]

    doing = client.post(reverse("api_v1:tasks:task-mark-doing", kwargs={"pk": pk}))
    assert doing.status_code == status.HTTP_200_OK
    assert doing.json()["status"] == "doing"

    promoted = client.post(
        reverse("api_v1:tasks:task-promote-priority", kwargs={"pk": pk})
    )
    assert promoted.json()["importance"] == "medium"

    done = client.post(reverse("api_v1:tasks:task-mark-done", kwargs={"pk": pk}))
    assert done.status_code == status.HTTP_200_OK
    assert done.json()["status"] == "done"
    assert TaskModel.objects.get(pk=pk).status == "done"


def test_completing_a_task_twice_is_a_conflict(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    pk = _create_task(client)["id"]
    url = reverse("api_v1:tasks:task-mark-done", kwargs={"pk": pk})
    client.post(url)

    repeated = client.post(url)
    restarted = client.post(reverse("api_v1:tasks:task-mark-doing", kwargs={"pk": pk}))

    assert repeated.status_code == status.HTTP_409_CONFLICT
    assert restarted.status_code == status.HTTP_409_CONFLICT
    assert repeated.data["error"]["message"] == "Task is already marked as done."
    assert repeated.data["detail"] == "Task is already marked as done."


def test_promoting_priority_saturates_at_high(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    pk = _create_task(client, importance="low")["id"]
    url = reverse("api_v1:tasks:task-promote-priority", kwargs={"pk": pk})

    promoted = [client.post(url).json()["importance"] for _ in range(4)]

    assert promoted == ["medium", "high", "high", "high"]
    assert TaskModel.objects.get(pk=pk).importance == "high"


# --- goals -----------------------------------------------------------------


def test_goal_crud_and_task_association(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    goal = _create_goal(client)
    task = _create_task(client)
    goal_url = reverse("api_v1:tasks:goal-detail", kwargs={"pk": goal["id"]})

    assert goal["task_count"] == 0
    assert client.get(goal_url).json()["name"] == "Spring cleaning"

    linked = client.post(
        reverse("api_v1:tasks:goal-link-task", kwargs={"pk": goal["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert linked.status_code == status.HTTP_200_OK
    assert linked.json()["goal_id"] == goal["id"]
    assert client.get(goal_url).json()["task_count"] == 1

    duplicated = client.post(
        reverse("api_v1:tasks:goal-link-task", kwargs={"pk": goal["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert duplicated.status_code == status.HTTP_400_BAD_REQUEST

    renamed = client.patch(goal_url, {"name": "Autumn cleaning"}, format="json")
    assert renamed.json()["name"] == "Autumn cleaning"
    assert renamed.json()["description"] == "Deep clean"

    unlinked = client.post(
        reverse("api_v1:tasks:goal-unlink-task", kwargs={"pk": goal["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert unlinked.json()["goal_id"] is None

    assert client.delete(goal_url).status_code == status.HTTP_204_NO_CONTENT
    assert GoalModel.objects.count() == 0


def test_deleting_a_goal_keeps_its_tasks(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    goal = _create_goal(client)
    task = _create_task(client)
    client.post(
        reverse("api_v1:tasks:goal-link-task", kwargs={"pk": goal["id"]}),
        {"task_id": task["id"]},
        format="json",
    )

    client.delete(reverse("api_v1:tasks:goal-detail", kwargs={"pk": goal["id"]}))

    remaining = client.get(
        reverse("api_v1:tasks:task-detail", kwargs={"pk": task["id"]})
    )
    assert remaining.status_code == status.HTTP_200_OK
    assert remaining.json()["goal_id"] is None


def test_foreign_goals_are_invisible(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    foreign_goal: Any = GoalFactory(user=UserFactory())
    foreign_task: Any = TaskFactory(user=UserFactory())
    client = _client(owner, jwt_token_factory)
    goal_url = reverse("api_v1:tasks:goal-detail", kwargs={"pk": foreign_goal.id})

    assert client.get(goal_url).status_code == status.HTTP_404_NOT_FOUND
    assert (
        client.post(
            reverse("api_v1:tasks:goal-link-task", kwargs={"pk": foreign_goal.id}),
            {"task_id": foreign_task.id},
            format="json",
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert client.get(reverse("api_v1:tasks:goal-list")).json() == []
    assert (
        client.post(
            reverse("api_v1:tasks:goal-link-task", kwargs={"pk": foreign_goal.id}),
            {"task_id": _create_task(client)["id"]},
            format="json",
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_unlinking_a_task_that_is_not_linked_is_rejected(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    goal = _create_goal(client)
    task = _create_task(client)

    response = client.post(
        reverse("api_v1:tasks:goal-unlink-task", kwargs={"pk": goal["id"]}),
        {"task_id": task["id"]},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# --- daily plans -----------------------------------------------------------


def test_daily_plan_crud_and_scheduling(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    plan = _open_plan(client, TODAY)
    task = _create_task(client, estimated_hours="2.00")
    plan_url = reverse("api_v1:tasks:dailyplan-detail", kwargs={"pk": plan["id"]})

    assert plan["tasks"] == []
    assert plan["total_hours"] == "0.00"
    assert plan["is_full"] is False
    assert plan["generated_by_llm"] is False

    added = client.post(
        reverse("api_v1:tasks:dailyplan-add-task", kwargs={"pk": plan["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert added.status_code == status.HTTP_200_OK
    assert added.json()["total_hours"] == "2.00"
    assert [item["id"] for item in added.json()["tasks"]] == [task["id"]]
    assert DailyPlanModel.objects.get(pk=plan["id"]).total_hours == Decimal("2.00")

    duplicated = client.post(
        reverse("api_v1:tasks:dailyplan-add-task", kwargs={"pk": plan["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert duplicated.status_code == status.HTTP_409_CONFLICT

    flagged = client.patch(plan_url, {"generated_by_llm": True}, format="json")
    assert flagged.json()["generated_by_llm"] is True

    removed = client.post(
        reverse("api_v1:tasks:dailyplan-remove-task", kwargs={"pk": plan["id"]}),
        {"task_id": task["id"]},
        format="json",
    )
    assert removed.json()["total_hours"] == "0.00"
    assert removed.json()["tasks"] == []

    assert client.delete(plan_url).status_code == status.HTTP_204_NO_CONTENT
    assert TaskModel.objects.filter(pk=task["id"]).exists()


def test_scheduling_beyond_the_daily_budget_is_a_conflict(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    plan = _open_plan(client, TODAY)
    first = _create_task(client, name="First", estimated_hours="4.00")
    second = _create_task(client, name="Second", estimated_hours="4.00")
    third = _create_task(client, name="Third", estimated_hours="1.00")
    add_url = reverse("api_v1:tasks:dailyplan-add-task", kwargs={"pk": plan["id"]})

    client.post(add_url, {"task_id": first["id"]}, format="json")
    client.post(add_url, {"task_id": second["id"]}, format="json")
    rejected = client.post(add_url, {"task_id": third["id"]}, format="json")

    assert rejected.status_code == status.HTTP_409_CONFLICT
    assert DailyPlanModel.objects.get(pk=plan["id"]).tasks.count() == 2


def test_removing_a_task_that_is_not_scheduled_is_a_conflict(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    plan = _open_plan(client, TODAY)
    task = _create_task(client)

    response = client.post(
        reverse("api_v1:tasks:dailyplan-remove-task", kwargs={"pk": plan["id"]}),
        {"task_id": task["id"]},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_opening_the_same_day_twice_reuses_the_plan(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    first = _open_plan(client, TODAY)
    second = _open_plan(client, TODAY)

    assert first["id"] == second["id"]
    assert DailyPlanModel.objects.count() == 1


def test_daily_plan_list_covers_today_and_an_explicit_range(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_url = reverse("api_v1:tasks:dailyplan-list")
    _open_plan(client, TODAY)
    _open_plan(client, TODAY - timedelta(days=2))

    today_only = client.get(list_url)
    ranged = client.get(
        list_url,
        {
            "start_date": (TODAY - timedelta(days=3)).isoformat(),
            "end_date": (TODAY - timedelta(days=1)).isoformat(),
        },
    )

    assert [item["date"] for item in today_only.json()] == [TODAY.isoformat()]
    assert len(ranged.json()) == 1

    inverted = client.get(
        list_url,
        {
            "start_date": TODAY.isoformat(),
            "end_date": (TODAY - timedelta(days=1)).isoformat(),
        },
    )
    assert inverted.status_code == status.HTTP_400_BAD_REQUEST


def test_foreign_daily_plans_are_invisible(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    stranger: Any = UserFactory()
    foreign: Any = DailyPlanFactory(user=stranger)
    client = _client(owner, jwt_token_factory)
    plan_url = reverse("api_v1:tasks:dailyplan-detail", kwargs={"pk": foreign.id})

    assert client.get(plan_url).status_code == status.HTTP_404_NOT_FOUND
    assert (
        client.post(
            reverse("api_v1:tasks:dailyplan-add-task", kwargs={"pk": foreign.id}),
            {"task_id": _create_task(client)["id"]},
            format="json",
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert client.delete(plan_url).status_code == status.HTTP_404_NOT_FOUND
    assert client.get(reverse("api_v1:tasks:dailyplan-list")).json() == []
