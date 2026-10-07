"""Celery tasks for asynchronous assistant assistance.

Every LLM call in the project happens here, never in a view or a use case, so an
HTTP request only ever enqueues work and returns.

Two properties are deliberate:

* **Assistants are optional.** A missing, unreachable, or badly-behaved provider
  must never surface as a failed request. The use cases already record the
  failure on the entity; these tasks translate that into a log line and a
  ``failed`` status, and they never re-raise it.
* **Retries cover the database, not the model.** ``OperationalError`` is
  transient and worth retrying with backoff. ``LlmUnavailableError`` is not: the
  daemon is simply not there, and retrying a prompt that costs inference time
  five times helps nobody. Those degrade immediately instead.
"""

import logging
from datetime import date
from typing import Any
from uuid import UUID

from celery import shared_task
from django.conf import settings as django_settings
from django.db import OperationalError, transaction

from apps.tasks.application.use_cases import (
    DecomposeOverwhelmingTask,
    EvaluateTaskWithLlm,
    GenerateDailyPlanWithLlm,
)
from apps.tasks.infrastructure.adapters.ollama_client import (
    OllamaClient,
    settings_from_environment,
)
from apps.tasks.infrastructure.persistence.repositories import (
    DjangoDailyPlanRepository,
    DjangoGoalRepository,
    DjangoTaskRepository,
)
from shared.infrastructure.clock import SystemClock

logger = logging.getLogger(__name__)


def build_llm_client() -> OllamaClient:
    """Build the assistant client from Django settings.

    Reading settings here rather than in the adapter keeps ``os.environ`` out of
    the adapter and lets tests override ``settings.OLLAMA_BASE_URL``.
    """
    return OllamaClient(
        settings=settings_from_environment(
            getattr(django_settings, "OLLAMA_BASE_URL", None),
            getattr(django_settings, "OLLAMA_MODEL", None),
        )
    )


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def evaluate_task_celery(
    self: Any, task_id: str, force: bool = False
) -> dict[str, Any]:
    """Assess one task's importance and effort.

    ``force`` re-evaluates a task that already carries an assessment, which is
    what the manual trigger sends: the owner asking twice is a deliberate act,
    and skipping silently would read as a broken button.
    """
    parsed_task_id = UUID(task_id)
    use_case = EvaluateTaskWithLlm(
        DjangoTaskRepository(),
        build_llm_client(),
        SystemClock(),
    )
    logger.info(
        "task evaluation started task_id=%s force=%s task_id_run=%s",
        parsed_task_id,
        force,
        self.request.id,
    )
    outcome = use_case.execute(parsed_task_id, force=force)
    if outcome.is_failure:
        logger.warning(
            "task evaluation degraded task_id=%s reason=assistant_unavailable",
            parsed_task_id,
        )
    logger.info(
        "task evaluation finished task_id=%s outcome=%s",
        parsed_task_id,
        outcome.status,
    )
    return {
        "task_id": task_id,
        "outcome": outcome.status,
        "is_checked_by_llm": bool(
            outcome.task is not None and outcome.task.is_checked_by_llm
        ),
    }


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def decompose_overwhelming_task_celery(self: Any, task_id: str) -> dict[str, Any]:
    """Break one too-big task into a goal and its subtasks."""
    parsed_task_id = UUID(task_id)
    use_case = DecomposeOverwhelmingTask(
        DjangoTaskRepository(),
        DjangoGoalRepository(),
        build_llm_client(),
        SystemClock(),
    )
    logger.info(
        "task decomposition started task_id=%s task_run=%s",
        parsed_task_id,
        self.request.id,
    )
    # Creating the goal, its subtasks, and closing the original is one decision.
    # Without this, a failure halfway would leave orphaned subtasks.
    with transaction.atomic():
        outcome = use_case.execute(parsed_task_id)
    if outcome.is_failure:
        logger.warning(
            "task decomposition degraded task_id=%s reason=assistant_unavailable",
            parsed_task_id,
        )
    logger.info(
        "task decomposition finished task_id=%s outcome=%s subtasks=%s",
        parsed_task_id,
        outcome.status,
        len(outcome.subtasks),
    )
    return {
        "task_id": task_id,
        "outcome": outcome.status,
        "subtasks_created": len(outcome.subtasks),
    }


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def generate_daily_plan_celery(
    self: Any, user_id: str, target_date: str
) -> dict[str, Any]:
    """Fill one day of a user's backlog with the assistant's selection."""
    parsed_user_id = UUID(user_id)
    plan_date = date.fromisoformat(target_date)
    use_case = GenerateDailyPlanWithLlm(
        DjangoDailyPlanRepository(),
        DjangoTaskRepository(),
        build_llm_client(),
        SystemClock(),
    )
    logger.info(
        "daily plan generation started user_id=%s date=%s task_run=%s",
        parsed_user_id,
        plan_date,
        self.request.id,
    )
    with transaction.atomic():
        outcome = use_case.execute(parsed_user_id, plan_date)
    if outcome.is_failure:
        logger.warning(
            "daily plan generation degraded user_id=%s date=%s "
            "reason=assistant_unavailable",
            parsed_user_id,
            plan_date,
        )
    logger.info(
        "daily plan generation finished user_id=%s date=%s outcome=%s",
        parsed_user_id,
        plan_date,
        outcome.status,
    )
    return {
        "user_id": user_id,
        "date": target_date,
        "outcome": outcome.status,
        "scheduled": len(outcome.scheduled_task_ids),
    }


__all__ = (
    "build_llm_client",
    "decompose_overwhelming_task_celery",
    "evaluate_task_celery",
    "generate_daily_plan_celery",
)
