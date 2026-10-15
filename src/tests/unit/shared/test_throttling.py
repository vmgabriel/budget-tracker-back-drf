"""Unit tests for the shared request throttles."""

from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from rest_framework.settings import api_settings
from rest_framework.test import APIRequestFactory
from rest_framework.throttling import SimpleRateThrottle

from shared.infrastructure.throttling import (
    LoginRateThrottle,
    RegisterRateThrottle,
    ScopedRateThrottle,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear_throttle_counters() -> None:
    """Start every test with an empty throttle history."""
    cache.clear()


def _request(ip: str = "203.0.113.10", forwarded_for: str | None = None) -> HttpRequest:
    """Build a request as DRF would receive it from a client."""
    factory = APIRequestFactory()
    meta: dict[str, Any] = {"REMOTE_ADDR": ip}
    if forwarded_for is not None:
        meta["HTTP_X_FORWARDED_FOR"] = forwarded_for
    request: HttpRequest = factory.post("/api/v1/auth/token/", {}, **meta)
    return request


def _view() -> Any:  # noqa: ANN401
    """Return a stand-in view; throttles only use it for scope metadata."""

    class _View:
        pass

    return _View()


class TestScopes:
    def test_login_throttle_uses_the_login_scope(self) -> None:
        assert LoginRateThrottle.scope == "login"

    def test_register_throttle_uses_the_register_scope(self) -> None:
        assert RegisterRateThrottle.scope == "register"

    def test_both_are_simple_rate_throttles(self) -> None:
        assert issubclass(LoginRateThrottle, SimpleRateThrottle)
        assert issubclass(ScopedRateThrottle, SimpleRateThrottle)

    def test_a_scope_can_be_supplied_at_construction(self) -> None:
        assert ScopedRateThrottle(scope="login").scope == "login"

    def test_a_scope_without_a_configured_rate_is_rejected(self) -> None:
        # DRF refuses an unknown scope rather than silently allowing
        # everything, which is the failure mode worth catching in a test.
        with pytest.raises(ImproperlyConfigured, match="No default throttle rate"):
            _ = ScopedRateThrottle(scope="no-such-scope").get_rate()

    def test_a_throttle_without_a_scope_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="scope"):
            ScopedRateThrottle()

    def test_rates_come_from_settings(self) -> None:
        assert api_settings.DEFAULT_THROTTLE_RATES["login"] == "10/minute"
        assert api_settings.DEFAULT_THROTTLE_RATES["register"] == "5/hour"
        assert api_settings.DEFAULT_THROTTLE_RATES["anon"] == "100/hour"
        assert api_settings.DEFAULT_THROTTLE_RATES["user"] == "1000/hour"


class TestAllowRequest:
    def test_allows_up_to_the_limit_then_rejects(self) -> None:
        throttle = LoginRateThrottle()
        request = _request()
        request.user = AnonymousUser()

        assert [throttle.allow_request(request, _view()) for _ in range(10)] == [
            True
        ] * 10
        assert throttle.allow_request(request, _view()) is False

    def test_the_limit_is_scoped(self) -> None:
        request = _request()
        request.user = AnonymousUser()

        assert LoginRateThrottle().allow_request(request, _view()) is True
        # Register has its own counter, so exhausting login must not register.
        assert RegisterRateThrottle().allow_request(request, _view()) is True

    def test_different_clients_have_independent_budgets(self) -> None:
        first = _request(ip="203.0.113.10")
        first.user = AnonymousUser()
        second = _request(ip="198.51.100.7")
        second.user = AnonymousUser()

        login = LoginRateThrottle()
        for _ in range(10):
            login.allow_request(first, _view())

        assert login.allow_request(first, _view()) is False
        assert login.allow_request(second, _view()) is True


class TestClientIdentification:
    def test_anonymous_requests_are_keyed_by_address(self) -> None:
        throttle = LoginRateThrottle()
        request = _request(ip="203.0.113.10")
        request.user = AnonymousUser()

        assert (
            throttle.get_cache_key(request, _view()) == "throttle_login_ip:203.0.113.10"
        )

    def test_authenticated_requests_are_keyed_by_account(self) -> None:
        throttle = LoginRateThrottle()
        request = _request(ip="203.0.113.10")
        request.user = type("User", (), {"is_authenticated": True, "pk": "user-id"})()

        assert throttle.get_cache_key(request, _view()) == "throttle_login_user:user-id"

    def test_an_account_behind_one_nat_does_not_share_a_bucket(self) -> None:
        # Two household members behind one router must not exhaust each other's
        # budget, which is why the authenticated key is the account.
        throttle = LoginRateThrottle()
        first = _request(ip="203.0.113.10")
        first.user = type("User", (), {"is_authenticated": True, "pk": "first"})()
        second = _request(ip="203.0.113.10")
        second.user = type("User", (), {"is_authenticated": True, "pk": "second"})()

        assert throttle.get_cache_key(first, _view()) != throttle.get_cache_key(
            second, _view()
        )

    def test_without_a_proxy_count_the_peer_address_is_used(
        self, settings: Any
    ) -> None:
        # With the proxy count at zero, a forwarded header is untrusted, so the
        # immediate peer is the only defensible identity.
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 0}
        throttle = LoginRateThrottle()
        request = _request(ip="10.0.0.5", forwarded_for="203.0.113.10")
        request.user = AnonymousUser()

        assert throttle.get_ident(request) == "10.0.0.5"

    def test_with_one_proxy_the_forwarded_client_address_is_used(
        self, settings: Any
    ) -> None:
        # A single proxy appends the address it received from, so the header
        # holds exactly one entry: the client's.
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
        throttle = LoginRateThrottle()
        request = _request(ip="10.0.0.5", forwarded_for="203.0.113.10")
        request.user = AnonymousUser()

        assert throttle.get_ident(request) == "203.0.113.10"

    def test_with_two_proxies_the_client_is_the_second_to_last_entry(
        self, settings: Any
    ) -> None:
        settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 2}
        throttle = LoginRateThrottle()
        request = _request(ip="10.0.0.5", forwarded_for="203.0.113.10, 198.51.100.3")
        request.user = AnonymousUser()

        assert throttle.get_ident(request) == "203.0.113.10"
