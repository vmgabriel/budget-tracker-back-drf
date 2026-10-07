"""Unit tests for the Celery beat schedule parser."""

import pytest

from config.schedules import DEFAULT_DAILY_PLAN_CRON, parse_daily_plan_cron

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("0 6 * * *", (6, 0)),
        ("30 7 * * *", (7, 30)),
        ("  0   6   *  *  *  ", (6, 0)),
    ],
    ids=["default", "custom", "extra-whitespace"],
)
def test_parses_a_daily_cron(expression: str, expected: tuple[int, int]) -> None:
    schedule = parse_daily_plan_cron(expression)

    assert (schedule.hour, schedule.minute) == ({expected[0]}, {expected[1]})


def test_the_default_expression_is_six_in_the_morning() -> None:
    schedule = parse_daily_plan_cron(DEFAULT_DAILY_PLAN_CRON)

    assert (schedule.hour, schedule.minute) == ({6}, {0})


@pytest.mark.parametrize(
    "expression",
    ["0 6 * *", "0 6 * * * *", "", "every morning"],
    ids=["too-few", "too-many", "empty", "prose"],
)
def test_a_malformed_expression_falls_back_to_the_default(expression: str) -> None:
    """A typo must not stop the worker booting and lose every other task."""
    schedule = parse_daily_plan_cron(expression)

    assert (schedule.hour, schedule.minute) == ({6}, {0})


@pytest.mark.parametrize(
    "expression",
    ["0 6 1 * *", "0 6 * 3 *", "0 6 * * 1"],
    ids=["day-of-month", "month", "weekday"],
)
def test_a_non_daily_expression_falls_back_to_the_default(
    expression: str,
) -> None:
    """Only hour and minute may vary: this job plans one day at a time."""
    schedule = parse_daily_plan_cron(expression)

    assert (schedule.hour, schedule.minute) == ({6}, {0})


@pytest.mark.parametrize(
    "expression",
    ["a b * * *", "0 6 * * *x", "99 99 * * *"],
    ids=["words", "trailing-garbage", "out-of-range"],
)
def test_an_unusable_hour_or_minute_falls_back(expression: str) -> None:
    schedule = parse_daily_plan_cron(expression)

    assert (schedule.hour, schedule.minute) == ({6}, {0})


def test_a_wildcard_hour_or_minute_falls_back() -> None:
    """``0 * * * *`` would plan the day hourly, which is not a morning job."""
    schedule = parse_daily_plan_cron("0 * * * *")

    assert (schedule.hour, schedule.minute) == ({6}, {0})
