"""Shared SystemClock adapter tests."""

from datetime import UTC, datetime, timedelta

import pytest

from shared.infrastructure.clock import SystemClock

pytestmark = pytest.mark.unit


def test_system_clock_returns_utc_datetime_and_current_date() -> None:
    before = datetime.now(UTC)
    clock = SystemClock()
    current = clock.now()
    today = clock.today()
    after = datetime.now(UTC)

    assert before <= current <= after
    assert current.utcoffset() == timedelta(0)
    assert before.date() <= today <= after.date()
