"""Unit tests for the shared security headers middleware."""

from collections.abc import Callable
from typing import Any

import pytest
from django.http import HttpRequest, HttpResponse

from shared.infrastructure.middleware import (
    DEFAULT_SECURITY_HEADERS,
    SecurityHeadersMiddleware,
)

pytestmark = pytest.mark.unit


def _request() -> HttpRequest:
    """Return a bare request; the middleware never reads it."""
    return HttpRequest()


def _middleware(
    response: HttpResponse | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[SecurityHeadersMiddleware, Callable[[HttpRequest], HttpResponse]]:
    """Build the middleware around a stubbed downstream view."""
    final_response = response if response is not None else HttpResponse("ok")

    def get_response(request: HttpRequest) -> HttpResponse:
        del request
        return final_response

    return SecurityHeadersMiddleware(get_response, headers=headers), get_response


class TestHeadersAdded:
    def test_adds_the_default_header_set(self) -> None:
        middleware, _ = _middleware(headers=dict(DEFAULT_SECURITY_HEADERS))

        response = middleware(_request())

        assert response["X-Content-Type-Options"] == "nosniff"
        assert response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "camera=()" in response["Permissions-Policy"]
        assert "microphone=()" in response["Permissions-Policy"]
        assert "geolocation=()" in response["Permissions-Policy"]

    def test_the_body_is_left_untouched(self) -> None:
        middleware, _ = _middleware(HttpResponse("payload"))

        response = middleware(_request())

        assert response.content == b"payload"

    def test_a_custom_header_set_replaces_the_defaults(self) -> None:
        middleware, _ = _middleware(headers={"X-Frame-Options": "SAMEORIGIN"})

        response = middleware(_request())

        assert response["X-Frame-Options"] == "SAMEORIGIN"
        assert "Permissions-Policy" not in response


class TestSettingsDrivenConfiguration:
    def test_the_header_set_comes_from_settings_when_not_passed(
        self, settings: Any
    ) -> None:
        # Django builds middleware with get_response alone, so the deployment's
        # SECURITY_HEADERS setting has to be read inside the constructor.
        settings.SECURITY_HEADERS = {"X-Frame-Options": "SAMEORIGIN"}
        middleware, _ = _middleware()

        response = middleware(_request())

        assert response["X-Frame-Options"] == "SAMEORIGIN"
        assert "Permissions-Policy" not in response

    def test_the_project_settings_drive_the_headers(self, settings: Any) -> None:
        middleware, _ = _middleware()

        response = middleware(_request())

        for name, value in settings.SECURITY_HEADERS.items():
            if value:
                assert response[name] == value


class TestExistingHeaders:
    def test_does_not_overwrite_a_header_the_response_already_carries(self) -> None:
        # Django's SecurityMiddleware sets these from settings, and a reverse
        # proxy may set its own. Last writer wins in a response, so the inner
        # middleware must yield rather than fight.
        existing = HttpResponse("ok")
        existing["Referrer-Policy"] = "no-referrer"
        middleware, _ = _middleware(existing)

        response = middleware(_request())

        assert response["Referrer-Policy"] == "no-referrer"

    def test_still_fills_in_the_headers_that_are_absent(self) -> None:
        existing = HttpResponse("ok")
        existing["Referrer-Policy"] = "no-referrer"
        middleware, _ = _middleware(existing)

        response = middleware(_request())

        assert response["X-Content-Type-Options"] == "nosniff"

    def test_an_empty_value_removes_a_header(self) -> None:
        # An operator disabling a policy empties its value rather than editing
        # middleware.
        middleware, _ = _middleware(headers={"Permissions-Policy": ""})

        response = middleware(_request())

        assert "Permissions-Policy" not in response


class TestDefaultHeaderSet:
    def test_the_defaults_are_the_documented_policy(self) -> None:
        assert DEFAULT_SECURITY_HEADERS["X-Content-Type-Options"] == "nosniff"
        assert DEFAULT_SECURITY_HEADERS["X-Frame-Options"] == "DENY"
        assert (
            DEFAULT_SECURITY_HEADERS["Referrer-Policy"]
            == "strict-origin-when-cross-origin"
        )

    def test_the_permissions_policy_denies_the_obvious_abuse_targets(self) -> None:
        policy = DEFAULT_SECURITY_HEADERS["Permissions-Policy"]

        for feature in ("camera", "microphone", "geolocation", "payment", "usb"):
            assert f"{feature}=()" in policy
