"""Shared pytest configuration, including Celery and authentication fixtures."""

from tests.factories import jwt_token_factory  # noqa: F401

pytest_plugins = ("celery.contrib.pytest",)
