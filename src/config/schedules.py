"""Periodic schedules for Celery Beat.

Kept out of ``settings.py`` so the settings module stays declarative: it reads
``DAILY_PLAN_GENERATION_CRON`` as a string and hands the parsed schedule to
``CELERY_BEAT_SCHEDULE``.
"""

import logging

from celery.schedules import crontab

logger = logging.getLogger(__name__)

DEFAULT_DAILY_PLAN_CRON = "0 6 * * *"
CRON_FIELD_COUNT = 5
FALLBACK = "0 6 * * *"


def parse_daily_plan_cron(expression: str) -> crontab:
    """Turn a ``"minute hour day month weekday"`` string into a Celery crontab.

    Only the minute and hour fields may vary; the rest must be ``*``. This job
    plans one day at a time, so accepting a richer grammar would let someone
    configure ``0 6 1 * *`` and quietly get monthly planning instead.

    Anything unusable falls back to the default and logs a warning, because a
    typo in one environment variable should not stop the worker from booting
    and taking every other task down with it.
    """
    fields = expression.split()
    if len(fields) != CRON_FIELD_COUNT:
        return _fallback(expression, "it is not a 5-field cron expression")

    minute, hour, day_of_month, month_of_year, day_of_week = fields
    if (day_of_month, month_of_year, day_of_week) != ("*", "*", "*"):
        return _fallback(expression, "it schedules more than daily")
    try:
        return crontab(minute=_as_int(minute, "minute"), hour=_as_int(hour, "hour"))
    except ValueError:
        return _fallback(expression, "its hour or minute is not usable")


def _as_int(value: str, label: str) -> int:
    """Return ``value`` as an int, rejecting the ``*`` wildcard."""
    if value == "*":
        raise ValueError(f"A wildcard {label} would run the job all day.")
    return int(value)


def _fallback(expression: str, reason: str) -> crontab:
    logger.warning(
        "DAILY_PLAN_GENERATION_CRON=%r is unusable because %s; using %r instead.",
        expression,
        reason,
        FALLBACK,
    )
    return parse_daily_plan_cron(FALLBACK)
