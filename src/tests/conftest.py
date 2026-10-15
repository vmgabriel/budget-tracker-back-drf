"""Shared pytest configuration, including Celery and authentication fixtures."""

import pytest
from django.core.cache import caches

from tests.factories import jwt_token_factory  # noqa: F401

pytest_plugins = ("celery.contrib.pytest",)


@pytest.fixture(autouse=True)
def clear_rate_limit_counters() -> None:
    """Start every test with empty throttle counters.

    Throttling is enabled in the test environment on purpose: it is HTTP
    behaviour that clients can observe, so it is tested rather than switched
    off. The counters, however, live in the shared cache, so without this
    fixture one test's requests would throttle an unrelated later test.
    """
    caches["default"].clear()
