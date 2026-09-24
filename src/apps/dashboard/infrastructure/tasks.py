"""Idempotent Celery tasks for dashboard summary generation."""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from functools import partial
from typing import Any
from uuid import UUID

from celery import shared_task
from django.apps import apps
from django.core.exceptions import ObjectDoesNotExist
from django.db import OperationalError, transaction

from apps.dashboard.application.use_cases import (
    GenerateDashboardSummary,
    GenerateDashboardSummaryCommand,
    InvalidateUserCache,
    InvalidateUserCacheCommand,
)
from apps.dashboard.domain.value_objects import Period, SummaryDate
from apps.dashboard.infrastructure.persistence.repositories import (
    DjangoDashboardSummaryRepository,
    DjangoTransactionReadRepository,
)
from shared.domain.ports.clock import Clock
from shared.infrastructure.clock import SystemClock

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _DashboardTaskUseCases:
    invalidate: InvalidateUserCache
    generate: GenerateDashboardSummary


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def reconcile_user_dashboards(self: Any) -> dict[str, object]:
    """Enqueue current-period refreshes for every active user.

    Transaction signals cover normal writes; this scheduled reconciliation also
    creates zero-valued snapshots after a day with no transaction activity.
    Each enqueued monthly task performs the normal daily and weekly rollups.
    """
    clock = SystemClock()
    today = clock.today()
    user_model = apps.get_model("users", "User")
    user_ids = list(
        user_model.objects.filter(is_active=True).values_list("pk", flat=True)
    )
    enqueued = 0
    for user_id in user_ids:
        # The monthly task rebuilds every daily row needed by the current
        # month, then rolls those rows up to the current week in one job.
        generate_monthly_summary.delay(str(user_id), today.isoformat())
        enqueued += 1
    logger.info(
        "dashboard reconciliation finished users=%s jobs=%s through=%s task_id=%s",
        len(user_ids),
        enqueued,
        today,
        self.request.id,
    )
    return {
        "users": len(user_ids),
        "jobs_enqueued": enqueued,
        "through": today.isoformat(),
    }


def _build_use_cases(clock: Clock) -> _DashboardTaskUseCases:
    summary_repository = DjangoDashboardSummaryRepository()
    return _DashboardTaskUseCases(
        invalidate=InvalidateUserCache(summary_repository, clock),
        generate=GenerateDashboardSummary(
            summary_repository,
            DjangoTransactionReadRepository(),
            clock,
        ),
    )


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def invalidate_user_dashboard_cache(
    self: Any,
    user_id: str,
    affected_dates: list[str],
) -> dict[str, object]:
    """Mark all periods affected by committed transaction changes stale."""
    parsed_user_id = UUID(user_id)
    parsed_dates = tuple(date.fromisoformat(value) for value in affected_dates)
    use_cases = _build_use_cases(SystemClock())
    logger.info(
        "dashboard invalidate started user_id=%s dates=%s task_id=%s",
        parsed_user_id,
        parsed_dates,
        self.request.id,
    )
    with transaction.atomic():
        if not _lock_user(parsed_user_id):
            return {
                "user_id": str(parsed_user_id),
                "invalidated": 0,
                "dates": [value.isoformat() for value in parsed_dates],
                "skipped": True,
            }
        changed = use_cases.invalidate.execute(
            InvalidateUserCacheCommand(parsed_user_id, parsed_dates)
        )
        transaction.on_commit(
            partial(
                _enqueue_daily_summaries,
                parsed_user_id,
                tuple(sorted(set(parsed_dates))),
            )
        )
    logger.info(
        "dashboard invalidate finished user_id=%s changed=%s task_id=%s",
        parsed_user_id,
        changed,
        self.request.id,
    )
    return {
        "user_id": str(parsed_user_id),
        "invalidated": changed,
        "dates": [value.isoformat() for value in parsed_dates],
    }


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def generate_daily_summary(
    self: Any,
    user_id: str,
    target_date: str,
) -> dict[str, object]:
    """Recalculate one day and enqueue its parent weekly rollup."""
    parsed_user_id = UUID(user_id)
    summary_date = date.fromisoformat(target_date)
    clock = SystemClock()
    if not _user_exists(parsed_user_id):
        return _skipped_result(parsed_user_id, Period.DAILY, summary_date)
    if summary_date > clock.today():
        return _skipped_result(parsed_user_id, Period.DAILY, summary_date)

    use_cases = _build_use_cases(clock)
    logger.info(
        "dashboard daily generation started user_id=%s date=%s task_id=%s",
        parsed_user_id,
        summary_date,
        self.request.id,
    )
    with transaction.atomic():
        if not _lock_user(parsed_user_id):
            return _skipped_result(parsed_user_id, Period.DAILY, summary_date)
        use_cases.invalidate.execute(
            InvalidateUserCacheCommand(parsed_user_id, (summary_date,))
        )
        summary = use_cases.generate.execute(
            GenerateDashboardSummaryCommand(
                parsed_user_id,
                Period.DAILY,
                summary_date,
            )
        )
        transaction.on_commit(
            partial(
                generate_weekly_summary.delay,
                str(parsed_user_id),
                summary_date.isoformat(),
            )
        )
    result = _summary_result(
        summary.period,
        summary.summary_date.value,
        summary.is_stale,
    )
    logger.info(
        "dashboard daily generation finished user_id=%s date=%s stale=%s task_id=%s",
        parsed_user_id,
        summary_date,
        summary.is_stale,
        self.request.id,
    )
    return result


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def generate_weekly_summary(
    self: Any,
    user_id: str,
    target_date: str,
) -> dict[str, object]:
    """Build a Monday-to-Sunday rollup from complete daily summaries."""
    parsed_user_id = UUID(user_id)
    summary_date = Period.WEEKLY.start(SummaryDate(date.fromisoformat(target_date)))
    clock = SystemClock()
    if not _user_exists(parsed_user_id):
        return _skipped_result(parsed_user_id, Period.WEEKLY, summary_date.value)
    if summary_date.value > clock.today():
        return _skipped_result(parsed_user_id, Period.WEEKLY, summary_date.value)

    use_cases = _build_use_cases(clock)
    affected_dates = _dates_through_today(
        summary_date.value,
        Period.WEEKLY.end(summary_date).value,
        clock.today(),
    )
    logger.info(
        "dashboard weekly generation started user_id=%s date=%s task_id=%s",
        parsed_user_id,
        summary_date.value,
        self.request.id,
    )
    with transaction.atomic():
        if not _lock_user(parsed_user_id):
            return _skipped_result(
                parsed_user_id,
                Period.WEEKLY,
                summary_date.value,
            )
        use_cases.invalidate.execute(
            InvalidateUserCacheCommand(parsed_user_id, affected_dates)
        )
        for affected_date in affected_dates:
            use_cases.generate.execute(
                GenerateDashboardSummaryCommand(
                    parsed_user_id,
                    Period.DAILY,
                    affected_date,
                )
            )
        summary = use_cases.generate.execute(
            GenerateDashboardSummaryCommand(
                parsed_user_id,
                Period.WEEKLY,
                summary_date.value,
            )
        )
        transaction.on_commit(
            partial(
                _enqueue_monthly_summaries,
                parsed_user_id,
                affected_dates,
            )
        )
    result = _summary_result(
        summary.period,
        summary.summary_date.value,
        summary.is_stale,
    )
    logger.info(
        "dashboard weekly generation finished user_id=%s date=%s stale=%s task_id=%s",
        parsed_user_id,
        summary_date.value,
        summary.is_stale,
        self.request.id,
    )
    return result


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def generate_monthly_summary(
    self: Any,
    user_id: str,
    target_date: str,
) -> dict[str, object]:
    """Build a calendar-month rollup from weekly and boundary-day summaries."""
    parsed_user_id = UUID(user_id)
    summary_date = Period.MONTHLY.start(SummaryDate(date.fromisoformat(target_date)))
    clock = SystemClock()
    if not _user_exists(parsed_user_id):
        return _skipped_result(parsed_user_id, Period.MONTHLY, summary_date.value)
    if summary_date.value > clock.today():
        return _skipped_result(parsed_user_id, Period.MONTHLY, summary_date.value)

    use_cases = _build_use_cases(clock)
    month_end = Period.MONTHLY.end(summary_date).value
    affected_dates = _dates_through_today(
        summary_date.value,
        month_end,
        clock.today(),
    )
    first_week = summary_date.value - timedelta(days=summary_date.value.weekday())
    affected_weeks = _dates_through_today(
        first_week,
        month_end,
        clock.today(),
        step=timedelta(days=7),
    )
    rollup_dates = set(affected_dates)
    for affected_week in affected_weeks:
        rollup_dates.update(
            _dates_through_today(
                affected_week,
                affected_week + timedelta(days=6),
                clock.today(),
            )
        )
    ordered_rollup_dates = tuple(sorted(rollup_dates))
    boundary_dates = tuple(sorted(rollup_dates - set(affected_dates)))
    logger.info(
        "dashboard monthly generation started user_id=%s date=%s task_id=%s",
        parsed_user_id,
        summary_date.value,
        self.request.id,
    )
    with transaction.atomic():
        if not _lock_user(parsed_user_id):
            return _skipped_result(
                parsed_user_id,
                Period.MONTHLY,
                summary_date.value,
            )
        use_cases.invalidate.execute(
            InvalidateUserCacheCommand(parsed_user_id, affected_dates)
        )
        if boundary_dates:
            use_cases.invalidate.execute(
                InvalidateUserCacheCommand(
                    parsed_user_id,
                    boundary_dates,
                    (Period.DAILY, Period.WEEKLY),
                )
            )
        for affected_date in ordered_rollup_dates:
            use_cases.generate.execute(
                GenerateDashboardSummaryCommand(
                    parsed_user_id,
                    Period.DAILY,
                    affected_date,
                )
            )
        for affected_week in affected_weeks:
            use_cases.generate.execute(
                GenerateDashboardSummaryCommand(
                    parsed_user_id,
                    Period.WEEKLY,
                    affected_week,
                )
            )
        summary = use_cases.generate.execute(
            GenerateDashboardSummaryCommand(
                parsed_user_id,
                Period.MONTHLY,
                summary_date.value,
            )
        )
    result = _summary_result(
        summary.period,
        summary.summary_date.value,
        summary.is_stale,
    )
    logger.info(
        "dashboard monthly generation finished user_id=%s date=%s stale=%s task_id=%s",
        parsed_user_id,
        summary_date.value,
        summary.is_stale,
        self.request.id,
    )
    return result


def _enqueue_daily_summaries(user_id: UUID, affected_dates: tuple[date, ...]) -> None:
    for affected_date in affected_dates:
        generate_daily_summary.delay(str(user_id), affected_date.isoformat())


def _enqueue_monthly_summaries(
    user_id: UUID,
    affected_dates: tuple[date, ...],
) -> None:
    month_starts = sorted({value.replace(day=1) for value in affected_dates})
    for month_start in month_starts:
        generate_monthly_summary.delay(str(user_id), month_start.isoformat())


def _dates_through_today(
    start: date,
    end: date,
    today: date,
    *,
    step: timedelta = timedelta(days=1),
) -> tuple[date, ...]:
    values: list[date] = []
    cursor = start
    through = min(end, today)
    while cursor <= through:
        values.append(cursor)
        cursor += step
    return tuple(values)


def _user_exists(user_id: UUID) -> bool:
    user_model = apps.get_model("users", "User")
    return bool(user_model.objects.filter(pk=user_id).exists())


def _lock_user(user_id: UUID) -> bool:
    user_model = apps.get_model("users", "User")
    try:
        user_model.objects.select_for_update().only("pk").get(pk=user_id)
    except ObjectDoesNotExist:
        return False
    return True


def _summary_result(
    period: Period, summary_date: date, is_stale: bool
) -> dict[str, object]:
    return {
        "period": period.value,
        "date": summary_date.isoformat(),
        "is_stale": is_stale,
    }


def _skipped_result(
    user_id: UUID,
    period: Period,
    summary_date: date,
) -> dict[str, object]:
    return {
        "user_id": str(user_id),
        "period": period.value,
        "date": summary_date.isoformat(),
        "skipped": True,
    }
