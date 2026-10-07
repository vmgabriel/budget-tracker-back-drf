"""Celery task integration tests for assistant assistance.

The assistant is replaced at the port boundary: ``OllamaClient`` is what the
tasks build, so patching it exercises the whole path from Celery argument
parsing through the use cases to committed rows, without a network call.

``CELERY_TASK_ALWAYS_EAGER`` is on for the test environment, so ``.delay(...)``
runs inline and the assertions below read real committed state.
"""

from datetime import date
from decimal import Decimal
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status
from rest_framework.test import APIClient

from apps.tasks.domain.value_objects import Priority, TaskStatus
from apps.tasks.infrastructure import tasks as task_infrastructure
from apps.tasks.infrastructure.persistence.models import (
    DailyPlanModel,
    GoalModel,
    TaskModel,
)
from apps.tasks.infrastructure.tasks import (
    decompose_overwhelming_task_celery,
    evaluate_task_celery,
    generate_daily_plan_celery,
    schedule_daily_plan_generation,
)
from tests.factories import ProfileFactory, TaskFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]

# factory-boy declares results as the factory class; the models are what
# these tests actually inspect, so the calls are widened once here.
_task = cast(Any, TaskFactory)
_user = cast(Any, UserFactory)

DAY = date(2026, 3, 2)
CLIENT_PATH = "apps.tasks.infrastructure.tasks.build_llm_client"

EVALUATION_PAYLOAD = {
    "importance": "high",
    "estimated_hours": 3.5,
    "suggested_goal": "Home admin",
}

DECOMPOSITION_PAYLOAD = {
    "goal_name": "Kitchen renovation",
    "subtasks": [
        {"name": "Measure cabinets", "description": "", "estimated_hours": 2.0},
        {
            "name": "Install cabinets",
            "description": "Level them.",
            "estimated_hours": 4.0,
        },
    ],
}


class StubAssistant:
    """Stand in for the Ollama client with canned or raising answers."""

    def __init__(
        self,
        evaluation: dict[str, Any] | None = None,
        decomposition: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        failure: Exception | None = None,
        available: bool = True,
    ) -> None:
        self.evaluation = evaluation
        self.decomposition = decomposition
        self.plan = plan
        self.failure = failure
        self.available = available
        self.calls: list[tuple[str, dict[str, Any]]] = []
        # The health endpoint reports the configured model, so the stub needs
        # the same shape the real client exposes.
        from apps.tasks.infrastructure.adapters.ollama_client import OllamaSettings

        self.settings = OllamaSettings()

    def evaluate_task(self, **kwargs: Any) -> Any:
        self.calls.append(("evaluate", kwargs))
        self._raise_if_failing()
        from apps.tasks.application.llm import parse_task_evaluation

        return parse_task_evaluation(self.evaluation or {})

    def decompose_task(self, **kwargs: Any) -> Any:
        self.calls.append(("decompose", kwargs))
        self._raise_if_failing()
        from apps.tasks.application.llm import parse_task_decomposition

        return parse_task_decomposition(self.decomposition or {})

    def plan_day(self, **kwargs: Any) -> Any:
        self.calls.append(("plan", kwargs))
        self._raise_if_failing()
        from apps.tasks.application.llm import parse_daily_plan_proposal

        # The use case offers TaskId values, not raw UUIDs.
        allowed = [row[0] for row in kwargs["candidates"]]
        return parse_daily_plan_proposal(self.plan or {}, allowed)

    def is_available(self) -> bool:
        return self.available

    def probe(self) -> Any:
        from apps.tasks.infrastructure.adapters.ollama_client import (
            AssistantAvailability,
        )

        return AssistantAvailability(
            self.available, None if self.available else "offline"
        )

    def _raise_if_failing(self) -> None:
        if self.failure is not None:
            raise self.failure


def _stub(**kwargs: Any) -> Any:
    """Patch the task module to build ``StubAssistant`` instead of a real one."""
    assistant = StubAssistant(**kwargs)
    return patch(CLIENT_PATH, return_value=assistant), assistant


# --- registration -----------------------------------------------------------


def test_celery_app_registers_assistant_tasks(celery_app: Any) -> None:
    assert "apps.tasks.infrastructure.tasks.evaluate_task_celery" in celery_app.tasks
    assert (
        "apps.tasks.infrastructure.tasks.decompose_overwhelming_task_celery"
        in celery_app.tasks
    )
    assert (
        "apps.tasks.infrastructure.tasks.generate_daily_plan_celery" in celery_app.tasks
    )
    assert (
        "apps.tasks.infrastructure.tasks.schedule_daily_plan_generation"
        in celery_app.tasks
    )


def test_beat_schedules_the_daily_plan_generation() -> None:
    # Read from Django settings rather than the ``celery_app`` fixture: that
    # fixture builds a throwaway app with Celery's own defaults, so it can
    # never show the project's schedule.
    from django.conf import settings

    entry: Any = settings.CELERY_BEAT_SCHEDULE["generate-daily-plans"]
    schedule = entry["schedule"]

    assert (
        entry["task"]
        == "apps.tasks.infrastructure.tasks.schedule_daily_plan_generation"
    )
    assert (schedule.hour, schedule.minute) == ({6}, {0})
    # A run still queued an hour later is stale and would duplicate the next day.
    assert entry["options"]["expires"] <= 60 * 60


def test_the_project_celery_app_registers_the_scheduler() -> None:
    """Guards a real failure mode: a worker that knows nothing about these tasks.

    They live in ``infrastructure.tasks``, which ``autodiscover_tasks`` does not
    scan, so the app config has to import them. Without that import the web
    process still works - it reaches the tasks through the views - and only the
    worker ends up empty, which is easy to miss.
    """
    from config.celery import app

    app.loader.import_default_modules()
    for name in (
        "evaluate_task_celery",
        "decompose_overwhelming_task_celery",
        "generate_daily_plan_celery",
        "schedule_daily_plan_generation",
    ):
        assert f"apps.tasks.infrastructure.tasks.{name}" in app.tasks


def test_scheduler_enqueues_one_job_per_active_user() -> None:
    first = _user()
    second = _user()
    _user(is_active=False)

    with patch.object(generate_daily_plan_celery, "delay") as delay:
        result = schedule_daily_plan_generation.run()

    assert result == {"users": 2, "jobs_enqueued": 2}
    assert {call.args[0] for call in delay.call_args_list} == {
        str(first.id),
        str(second.id),
    }


def test_scheduler_uses_each_users_local_calendar_day() -> None:
    """A UTC day would hand a user behind UTC tomorrow's plan at six in the morning."""
    tokyo = _user()
    cast(Any, ProfileFactory)(user=tokyo, timezone="Asia/Tokyo")

    with (
        patch.object(generate_daily_plan_celery, "delay") as delay,
        freeze_time("2026-03-02 20:30:00"),
    ):
        schedule_daily_plan_generation.run()

    # 20:30 UTC is already the following day in Tokyo.
    assert delay.call_args.args[1] == "2026-03-03"


def test_scheduler_falls_back_to_utc_without_a_profile_timezone() -> None:
    _user()

    with (
        patch.object(generate_daily_plan_celery, "delay") as delay,
        freeze_time("2026-03-02 20:30:00"),
    ):
        schedule_daily_plan_generation.run()

    assert delay.call_args.args[1] == "2026-03-02"


def test_scheduler_reads_the_user_list_once(
    django_assert_num_queries: Any,
) -> None:
    """It runs unattended, so it must not fan out one query per user."""
    _user()

    with (
        patch.object(generate_daily_plan_celery, "delay"),
        django_assert_num_queries(2),
    ):
        schedule_daily_plan_generation.run()


def test_client_settings_come_from_django_settings() -> None:
    with patch("django.conf.settings.OLLAMA_MODEL", "qwen3:8b"):
        assert task_infrastructure.build_llm_client().settings.model == "qwen3:8b"


# --- evaluation -------------------------------------------------------------


def test_evaluation_updates_the_task_fields() -> None:
    task = _task(importance=Priority.LOW.value, estimated_hours=Decimal("1.00"))

    patcher, _ = _stub(evaluation=EVALUATION_PAYLOAD)
    with patcher:
        result = evaluate_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    assert result["outcome"] == "applied"
    assert task.importance == Priority.HIGH.value
    assert task.estimated_hours == Decimal("3.50")
    assert task.is_checked_by_llm is True
    assert task.llm_evaluation_failed is False


def test_evaluation_sends_the_stored_task_content_to_the_assistant() -> None:
    task = _task(name="Renew passport", description="Expiring soon")

    patcher, assistant = _stub(evaluation=EVALUATION_PAYLOAD)
    with patcher:
        evaluate_task_celery.delay(str(task.id))

    call = assistant.calls[0][1]
    assert call["name"] == "Renew passport"
    assert call["description"] == "Expiring soon"


def test_evaluation_of_a_missing_task_reports_not_found() -> None:
    patcher, assistant = _stub(evaluation=EVALUATION_PAYLOAD)
    with patcher:
        result = evaluate_task_celery.delay(str(uuid4())).get()

    assert result["outcome"] == "not_found"
    assert assistant.calls == []


def test_evaluation_skips_a_task_already_checked() -> None:
    task = _task(is_checked_by_llm=True)

    patcher, assistant = _stub(evaluation=EVALUATION_PAYLOAD)
    with patcher:
        result = evaluate_task_celery.delay(str(task.id)).get()

    assert result["outcome"] == "already_checked"
    assert assistant.calls == []


def test_manual_evaluation_forces_a_recheck() -> None:
    task = _task(is_checked_by_llm=True)

    patcher, _ = _stub(evaluation=EVALUATION_PAYLOAD)
    with patcher:
        result = evaluate_task_celery.delay(str(task.id), True).get()

    task.refresh_from_db()
    assert result["outcome"] == "applied"
    assert task.is_checked_by_llm is True


def test_creating_a_task_does_not_call_the_assistant() -> None:
    """Assistance is requested explicitly, never as a side effect of creating.

    The task context has no ``post_save`` handler: creation queues no LLM work,
    which is what keeps task creation fast and predictable. Evaluation happens
    when the owner asks for it.
    """
    with patch(CLIENT_PATH) as build:
        task = _task()

    build.assert_not_called()
    task.refresh_from_db()
    assert task.is_checked_by_llm is False
    assert task.llm_evaluation_failed is False


def test_updating_a_task_does_not_call_the_assistant() -> None:
    """An owner edit must never be overwritten by a background evaluation."""
    task = _task(estimated_hours=Decimal("5.00"))

    with patch(CLIENT_PATH) as build:
        task.estimated_hours = Decimal("1.00")
        task.save()

    build.assert_not_called()


@pytest.mark.parametrize(
    "failure_name",
    ["LlmUnavailableError", "LlmInvalidResponseError"],
)
def test_evaluation_degrades_when_the_assistant_fails(failure_name: str) -> None:
    from apps.tasks.application import llm as llm_module

    failure = getattr(llm_module, failure_name)("assistant down")
    task = _task(importance=Priority.LOW.value, estimated_hours=Decimal("1.00"))

    patcher, _ = _stub(failure=failure)
    with patcher:
        result = evaluate_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    assert result["outcome"] == "failed"
    # Only the failure flag moves; the owner's estimate must survive.
    assert task.llm_evaluation_failed is True
    assert task.is_checked_by_llm is False
    assert task.importance == Priority.LOW.value
    assert task.estimated_hours == Decimal("1.00")


def test_an_unparseable_reply_degrades_without_raising() -> None:
    from apps.tasks.application.llm import LlmInvalidResponseError

    task = _task()
    patcher, _ = _stub(failure=LlmInvalidResponseError("not JSON"))
    with patcher:
        result = evaluate_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    assert result["outcome"] == "failed"
    assert task.llm_evaluation_failed is True


def test_assistant_tasks_retry_only_database_failures() -> None:
    """Asserted on configuration rather than by making a task actually fail.

    Raising a real ``OperationalError`` would run the whole backoff schedule,
    and eager mode retries inline, so the test would take seconds to prove
    something readable from the decorator.
    """
    from django.db import OperationalError

    from apps.tasks.application.llm import (
        LlmInvalidResponseError,
        LlmUnavailableError,
    )

    for task in (
        evaluate_task_celery,
        decompose_overwhelming_task_celery,
        generate_daily_plan_celery,
    ):
        assert OperationalError in task.autoretry_for
        assert task.max_retries > 0
        # An unreachable or unhelpful assistant is not transient: the daemon is
        # simply absent, and retrying the prompt would repeat a paid call.
        assert LlmUnavailableError not in task.autoretry_for
        assert LlmInvalidResponseError not in task.autoretry_for


# --- decomposition ----------------------------------------------------------


def test_decomposition_creates_a_goal_and_its_subtasks() -> None:
    task = _task(
        name="Renovate the kitchen",
        description="Replace cabinets",
        estimated_hours=Decimal("10.00"),
        due_date=DAY,
    )

    patcher, _ = _stub(decomposition=DECOMPOSITION_PAYLOAD)
    with patcher:
        result = decompose_overwhelming_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    goal = GoalModel.objects.get(user_id=task.user_id)
    subtasks = list(TaskModel.objects.filter(goal=goal).order_by("name"))
    assert result["outcome"] == "applied"
    assert result["subtasks_created"] == 2
    assert goal.name == "Kitchen renovation"
    assert goal.user_id == task.user_id
    assert [subtask.name for subtask in subtasks] == [
        "Install cabinets",
        "Measure cabinets",
    ]
    assert task.status == TaskStatus.DONE.value


def test_decomposition_subtasks_inherit_deadline_and_owner() -> None:
    task = _task(estimated_hours=Decimal("10.00"), due_date=DAY)

    patcher, _ = _stub(decomposition=DECOMPOSITION_PAYLOAD)
    with patcher:
        decompose_overwhelming_task_celery.delay(str(task.id))

    goal = GoalModel.objects.get(user_id=task.user_id)
    for subtask in TaskModel.objects.filter(goal=goal):
        assert subtask.user_id == task.user_id
        assert subtask.due_date == DAY
        assert subtask.importance == Priority.LOW.value
        assert subtask.status == TaskStatus.TODO.value


def test_decomposition_skips_a_task_that_already_fits() -> None:
    task = _task(estimated_hours=Decimal("1.00"))

    patcher, assistant = _stub(decomposition=DECOMPOSITION_PAYLOAD)
    with patcher:
        result = decompose_overwhelming_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    assert result["outcome"] == "not_overwhelming"
    assert assistant.calls == []
    assert GoalModel.objects.filter(user_id=task.user_id).count() == 0
    assert task.status == TaskStatus.TODO.value


def test_decomposition_degrades_and_creates_nothing_on_failure() -> None:
    from apps.tasks.application.llm import LlmUnavailableError

    task = _task(estimated_hours=Decimal("10.00"))

    patcher, _ = _stub(failure=LlmUnavailableError("down"))
    with patcher:
        result = decompose_overwhelming_task_celery.delay(str(task.id)).get()

    task.refresh_from_db()
    assert result["outcome"] == "failed"
    assert result["subtasks_created"] == 0
    assert task.llm_evaluation_failed is True
    assert task.status == TaskStatus.TODO.value
    assert GoalModel.objects.filter(user_id=task.user_id).count() == 0


# --- daily plan -------------------------------------------------------------


def test_plan_generation_fills_the_day_from_the_backlog() -> None:
    user = _user()
    chosen = _task(user=user, estimated_hours=Decimal("2.00"))
    _task(user=user, estimated_hours=Decimal("5.00"))

    patcher, _ = _stub(plan={"task_ids": [str(chosen.id)], "total_hours": 2.0})
    with patcher:
        result = generate_daily_plan_celery.delay(str(user.id), DAY.isoformat()).get()

    plan = DailyPlanModel.objects.get(user=user, date=DAY)
    assert result["outcome"] == "generated"
    assert plan.generated_by_llm is True
    assert plan.total_hours == Decimal("2.00")
    assert [task.pk for task in plan.tasks.all()] == [chosen.pk]


def test_plan_generation_offers_only_the_owners_unfinished_tasks() -> None:
    user = _user()
    todo = _task(user=user, status=TaskStatus.TODO.value)
    _task(user=user, status=TaskStatus.DONE.value)
    stranger = _task(estimated_hours=Decimal("1.00"))

    patcher, assistant = _stub(plan={"task_ids": [str(todo.id)], "total_hours": 1.0})
    with patcher:
        generate_daily_plan_celery.delay(str(user.id), DAY.isoformat())

    offered = {str(row[0]) for row in assistant.calls[0][1]["candidates"]}
    assert offered == {str(todo.id)}
    assert str(stranger.id) not in offered


def test_plan_generation_recomputes_hours_from_stored_estimates() -> None:
    """A model that miscounts must not write wrong hours into the day."""
    user = _user()
    task = _task(user=user, estimated_hours=Decimal("2.50"))

    patcher, _ = _stub(plan={"task_ids": [str(task.id)], "total_hours": 99.0})
    with patcher:
        generate_daily_plan_celery.delay(str(user.id), DAY.isoformat())

    plan = DailyPlanModel.objects.get(user=user, date=DAY)
    assert plan.total_hours == Decimal("2.50")


def test_plan_generation_degrades_without_touching_storage() -> None:
    from apps.tasks.application.llm import LlmUnavailableError

    user = _user()
    _task(user=user)

    patcher, _ = _stub(failure=LlmUnavailableError("down"))
    with patcher:
        result = generate_daily_plan_celery.delay(str(user.id), DAY.isoformat()).get()

    assert result["outcome"] == "failed"
    assert DailyPlanModel.objects.filter(user=user).count() == 0


def test_plan_generation_leaves_an_existing_day_alone_on_failure() -> None:
    from apps.tasks.application.llm import LlmInvalidResponseError

    user = _user()
    task = _task(user=user, estimated_hours=Decimal("2.00"))
    plan = DailyPlanModel.objects.create(
        user=user, date=DAY, total_hours=Decimal("2.00"), generated_by_llm=False
    )
    plan.tasks.add(task)

    patcher, _ = _stub(failure=LlmInvalidResponseError("garbage"))
    with patcher:
        result = generate_daily_plan_celery.delay(str(user.id), DAY.isoformat()).get()

    plan.refresh_from_db()
    assert result["outcome"] == "failed"
    assert plan.generated_by_llm is False
    assert list(plan.tasks.all()) == [task]


def test_plan_generation_ignores_a_hallucinated_task_id() -> None:
    user = _user()
    task = _task(user=user, estimated_hours=Decimal("2.00"))

    patcher, _ = _stub(
        plan={"task_ids": [str(uuid4()), str(task.id)], "total_hours": 2.0}
    )
    with patcher:
        generate_daily_plan_celery.delay(str(user.id), DAY.isoformat())

    plan = DailyPlanModel.objects.get(user=user, date=DAY)
    assert [row.pk for row in plan.tasks.all()] == [task.pk]


# --- HTTP interface ---------------------------------------------------------


def _client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def test_llm_routes_live_under_the_tasks_prefix() -> None:
    task_id = _task().id

    assert (
        reverse("api_v1:tasks:task-evaluate", kwargs={"pk": task_id})
        == f"/api/v1/tasks/tasks/{task_id}/evaluate/"
    )
    assert (
        reverse("api_v1:tasks:task-decompose", kwargs={"pk": task_id})
        == f"/api/v1/tasks/tasks/{task_id}/decompose/"
    )
    assert reverse("api_v1:tasks:task-llm-health") == "/api/v1/tasks/tasks/llm-health/"


def test_assistant_routes_require_authentication() -> None:
    task = _task()
    client = APIClient()

    assert (
        client.post(
            reverse("api_v1:tasks:task-evaluate", kwargs={"pk": task.id})
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.get(reverse("api_v1:tasks:task-llm-health")).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_evaluate_endpoint_accepts_and_queues(jwt_token_factory: Any) -> None:
    task = _task()
    client = _client(task.user, jwt_token_factory)

    with patch("apps.tasks.infrastructure.tasks.evaluate_task_celery.delay") as delay:
        response = client.post(
            reverse("api_v1:tasks:task-evaluate", kwargs={"pk": task.id})
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.json()["queued"] is True
    delay.assert_called_once_with(str(task.id), True)


def test_decompose_endpoint_accepts_and_queues(jwt_token_factory: Any) -> None:
    task = _task()
    client = _client(task.user, jwt_token_factory)

    with patch(
        "apps.tasks.infrastructure.tasks.decompose_overwhelming_task_celery.delay"
    ) as delay:
        response = client.post(
            reverse("api_v1:tasks:task-decompose", kwargs={"pk": task.id})
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    delay.assert_called_once_with(str(task.id))


def test_another_owners_task_answers_404_and_queues_nothing(
    jwt_token_factory: Any,
) -> None:
    stranger = _task()
    client = _client(_user(), jwt_token_factory)

    with patch("apps.tasks.infrastructure.tasks.evaluate_task_celery.delay") as delay:
        response = client.post(
            reverse("api_v1:tasks:task-evaluate", kwargs={"pk": stranger.id})
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    delay.assert_not_called()


def test_decompose_on_another_owners_task_answers_404(jwt_token_factory: Any) -> None:
    stranger = _task()
    client = _client(_user(), jwt_token_factory)

    with patch(
        "apps.tasks.infrastructure.tasks.decompose_overwhelming_task_celery.delay"
    ) as delay:
        response = client.post(
            reverse("api_v1:tasks:task-decompose", kwargs={"pk": stranger.id})
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    delay.assert_not_called()


def test_llm_health_reports_ok_when_the_provider_answers(
    jwt_token_factory: Any,
) -> None:
    client = _client(_user(), jwt_token_factory)

    with patch(CLIENT_PATH, return_value=StubAssistant(available=True)):
        response = client.get(reverse("api_v1:tasks:task-llm-health"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


def test_llm_health_reports_503_when_the_provider_is_down(
    jwt_token_factory: Any,
) -> None:
    client = _client(_user(), jwt_token_factory)

    with patch(CLIENT_PATH, return_value=StubAssistant(available=False)):
        response = client.get(reverse("api_v1:tasks:task-llm-health"))

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["status"] == "unavailable"
    assert response.json()["model"] is None


def test_evaluate_endpoint_answers_202_even_when_the_provider_is_down(
    jwt_token_factory: Any,
) -> None:
    """A dead assistant must never turn into a failed request."""
    task = _task()
    client = _client(task.user, jwt_token_factory)

    with patch(CLIENT_PATH, return_value=StubAssistant(available=False)):
        response = client.post(
            reverse("api_v1:tasks:task-evaluate", kwargs={"pk": task.id})
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    task.refresh_from_db()
    assert task.llm_evaluation_failed is True
