"""Unit tests for the production settings validators."""

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.validators import (
    MINIMUM_SECRET_KEY_LENGTH,
    validate_allowed_hosts,
    validate_debug,
    validate_production_settings,
    validate_query_logging,
    validate_secret_key,
)

pytestmark = pytest.mark.unit

_GOOD_SECRET = "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6A7B8C9D0"


class TestValidateSecretKey:
    def test_accepts_a_long_random_key_in_production(self) -> None:
        validate_secret_key(_GOOD_SECRET, environment="production")

    def test_rejects_the_checked_in_development_default(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="development default"):
            validate_secret_key(
                "unsafe-development-only-change-me-before-production",
                environment="production",
            )

    def test_rejects_a_django_insecure_prefix(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="development default"):
            validate_secret_key("django-insecure-" + "a" * 60, environment="production")

    def test_rejects_an_empty_key(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="empty"):
            validate_secret_key("", environment="production")

    def test_rejects_a_whitespace_key(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="empty"):
            validate_secret_key("   ", environment="production")

    def test_rejects_a_short_key(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="at least"):
            validate_secret_key(
                "a" * (MINIMUM_SECRET_KEY_LENGTH - 1), environment="production"
            )

    def test_rejects_a_long_but_repetitive_key(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="variety"):
            validate_secret_key("a" * 80, environment="production")

    def test_ignores_development_and_test_environments(self) -> None:
        # The Hatch and test environments use fixed keys on purpose; refusing
        # them would break local work without adding safety.
        validate_secret_key("unsafe-test-only-secret", environment="test")
        validate_secret_key("unsafe-development-only-secret", environment="local")


class TestValidateAllowedHosts:
    def test_accepts_an_explicit_allowlist(self) -> None:
        validate_allowed_hosts(["api.example.com"], environment="production")

    def test_rejects_an_empty_allowlist(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="required"):
            validate_allowed_hosts([], environment="production")

    def test_rejects_a_whitespace_only_allowlist(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="required"):
            validate_allowed_hosts(["  ", ""], environment="production")

    def test_rejects_a_wildcard_host(self) -> None:
        with pytest.raises(ImproperlyConfigured, match=r"\*"):
            validate_allowed_hosts(["*"], environment="production")

    def test_rejects_a_wildcard_among_valid_hosts(self) -> None:
        with pytest.raises(ImproperlyConfigured):
            validate_allowed_hosts(["api.example.com", "*"], environment="production")

    def test_rejects_the_test_client_host(self) -> None:
        with pytest.raises(ImproperlyConfigured):
            validate_allowed_hosts(["testserver"], environment="production")

    def test_ignores_non_production_environments(self) -> None:
        validate_allowed_hosts([], environment="local")
        validate_allowed_hosts(["*"], environment="test")


class TestValidateDebugAndQueryLogging:
    def test_rejects_debug_in_production(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="must be false"):
            validate_debug(True, environment="production")

    def test_allows_debug_outside_production(self) -> None:
        validate_debug(True, environment="local")
        validate_debug(False, environment="production")

    def test_rejects_query_logging_in_production(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="LOG_QUERIES"):
            validate_query_logging(True, environment="production")

    def test_allows_disabled_query_logging_everywhere(self) -> None:
        validate_query_logging(False, environment="production")
        validate_query_logging(True, environment="local")


class TestValidateProductionSettings:
    def test_accepts_a_complete_production_configuration(self) -> None:
        validate_production_settings(
            environment="production",
            secret_key=_GOOD_SECRET,
            allowed_hosts=["api.example.com"],
            debug=False,
        )

    def test_reports_the_first_problem_it_finds(self) -> None:
        # DEBUG is checked before the secret, so the message names the setting
        # an operator is most likely to have flipped by accident.
        with pytest.raises(ImproperlyConfigured, match="must be false"):
            validate_production_settings(
                environment="production",
                secret_key="unsafe-development-only-secret-that-is-long-enough",
                allowed_hosts=["*"],
                debug=True,
            )

    def test_reports_a_bad_secret_once_debug_is_fixed(self) -> None:
        with pytest.raises(ImproperlyConfigured, match="development default"):
            validate_production_settings(
                environment="production",
                secret_key="unsafe-development-only-secret-that-is-long-enough",
                allowed_hosts=["*"],
                debug=False,
            )

    def test_is_a_no_op_outside_production(self) -> None:
        validate_production_settings(
            environment="local",
            secret_key="unsafe-development-only-secret",
            allowed_hosts=[],
            debug=True,
            query_logging=True,
        )
