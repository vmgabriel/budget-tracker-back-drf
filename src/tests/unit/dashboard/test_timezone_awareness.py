"""Timezone conversion helpers and timezone-aware date anchoring."""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from apps.dashboard.application.use_cases import GetDashboardOverview
from apps.dashboard.domain.value_objects import (
    is_valid_timezone,
    utc_to_local_date,
)

from .fakes import FakeClock, FakeDashboardSummaryRepository

pytestmark = pytest.mark.unit


def test_utc_to_local_date_bogota_evening() -> None:
    # 7 PM in Bogotá (UTC-5) is midnight UTC the next day.
    utc_dt = datetime(2025, 3, 10, 0, 30, tzinfo=UTC)
    assert utc_to_local_date(utc_dt, "America/Bogota") == date(2025, 3, 9)


def test_utc_to_local_date_tokyo_morning() -> None:
    # 6 AM in Tokyo (UTC+9) is 9 PM UTC the previous day.
    utc_dt = datetime(2025, 3, 10, 21, 0, tzinfo=UTC)
    assert utc_to_local_date(utc_dt, "Asia/Tokyo") == date(2025, 3, 11)


def test_utc_to_local_date_utc_identity() -> None:
    utc_dt = datetime(2025, 3, 10, 12, 0, tzinfo=UTC)
    assert utc_to_local_date(utc_dt, "UTC") == date(2025, 3, 10)


def test_utc_to_local_date_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        utc_to_local_date(datetime(2025, 3, 10, 12, 0), "UTC")


def test_utc_to_local_date_rejects_unknown_timezone() -> None:
    with pytest.raises(ValueError, match="Unknown timezone"):
        utc_to_local_date(datetime(2025, 3, 10, 12, 0, tzinfo=UTC), "Mars/Olympus")


def test_is_valid_timezone() -> None:
    assert is_valid_timezone("America/Bogota")
    assert is_valid_timezone("UTC")
    assert not is_valid_timezone("Mars/Olympus")
    assert not is_valid_timezone("")


def test_overview_uses_user_local_date_as_anchor() -> None:
    # 2 AM UTC on Jan 15 is still Jan 14 in Bogotá.
    clock = FakeClock(datetime(2025, 1, 15, 2, 0, tzinfo=UTC))
    overview = GetDashboardOverview(FakeDashboardSummaryRepository(), clock)

    result = overview.execute(uuid4(), "America/Bogota")

    assert result.as_of_date == date(2025, 1, 14)


def test_overview_rejects_invalid_timezone() -> None:
    from apps.dashboard.application.exceptions import InvalidDashboardQuery

    overview = GetDashboardOverview(FakeDashboardSummaryRepository(), FakeClock())
    with pytest.raises(InvalidDashboardQuery):
        overview.execute(uuid4(), "Mars/Olympus")
