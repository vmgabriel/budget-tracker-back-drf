"""Unit tests for the shared HTTP middleware."""

import logging
from collections.abc import Callable
from typing import Any

import pytest
from django.http import HttpRequest, HttpResponse

from shared.infrastructure.logging import current_log_context
from shared.infrastructure.middleware import (
    DEFAULT_SECURITY_HEADERS,
    MAX_REQUEST_ID_LENGTH,
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    SecurityHeadersMiddleware,
    new_request_id,
    sanitize_request_id,
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


def _api_request(
    *,
    path: str = "/api/v1/tasks/",
    method: str = "GET",
    request_id: str | None = None,
) -> HttpRequest:
    """Build a request that looks like one the API actually receives."""
    request = HttpRequest()
    request.path = path
    request.method = method
    if request_id is not None:
        # HttpHeaders is read-only; the WSGI environ is what a real header
        # populates, and what HttpHeaders reads from.
        request.META[f"HTTP_{REQUEST_ID_HEADER.upper().replace('-', '_')}"] = request_id
    return request


def _user(pk: int | None, *, authenticated: bool = True) -> Any:
    """Build a minimal stand-in for ``request.user``."""

    class _User:
        def __init__(self) -> None:
            self.pk = pk
            self.is_authenticated = authenticated

    return _User()


def _id_middleware(
    get_response: Callable[[HttpRequest], HttpResponse] | None = None,
) -> RequestIdMiddleware:
    """Build the middleware around a trivial downstream view."""
    final = (
        get_response
        if get_response is not None
        else (lambda request: HttpResponse("ok"))
    )
    return RequestIdMiddleware(final)


class TestRequestIdGeneration:
    def test_generates_a_uuid_when_the_header_is_absent(self) -> None:
        generated = _id_middleware()(_api_request())[REQUEST_ID_HEADER]

        assert len(generated) == 36
        assert generated.count("-") == 4

    def test_two_requests_do_not_share_an_id(self) -> None:
        middleware = _id_middleware()

        first = middleware(_api_request())[REQUEST_ID_HEADER]
        second = middleware(_api_request())[REQUEST_ID_HEADER]

        assert first != second

    def test_the_id_is_also_exposed_on_the_request(self) -> None:
        request = _api_request()

        response = _id_middleware()(request)

        assert request.request_id == response[REQUEST_ID_HEADER]  # type: ignore[attr-defined]


class TestRequestIdPropagation:
    def test_an_inbound_id_is_preserved_so_a_proxy_trace_survives(self) -> None:
        response = _id_middleware()(_api_request(request_id="edge-abc-123"))

        assert response[REQUEST_ID_HEADER] == "edge-abc-123"

    def test_a_hostile_inbound_id_is_sanitized_not_rejected(self) -> None:
        response = _id_middleware()(_api_request(request_id="evil id\r\n\u001b[2J"))

        sanitized = response[REQUEST_ID_HEADER]
        assert "\n" not in sanitized
        assert "\r" not in sanitized
        assert "\x1b" not in sanitized
        assert sanitized, "the request is still served, with a cleaned-up id"

    def test_an_oversized_id_is_truncated(self) -> None:
        response = _id_middleware()(_api_request(request_id="a" * 500))

        assert len(response[REQUEST_ID_HEADER]) == MAX_REQUEST_ID_LENGTH

    def test_an_id_that_sanitizes_to_nothing_is_replaced(self) -> None:
        response = _id_middleware()(_api_request(request_id="///"))

        assert response[REQUEST_ID_HEADER] != "///"
        assert response[REQUEST_ID_HEADER]


class TestLogContextBinding:
    def test_the_context_is_bound_while_the_view_runs(self) -> None:
        seen: dict[str, Any] = {}

        def view(request: HttpRequest) -> HttpResponse:
            seen.update(current_log_context())
            return HttpResponse("ok")

        response = _id_middleware(view)(_api_request(path="/api/v1/x/", method="POST"))

        assert seen["request_id"] == response[REQUEST_ID_HEADER]
        assert seen["path"] == "/api/v1/x/"
        assert seen["method"] == "POST"

    def test_the_context_is_cleared_afterwards(self) -> None:
        # The worker thread is reused: a leftover id would tag the next request
        # served by it with the previous one's identifier.
        _id_middleware()(_api_request(request_id="first"))

        assert current_log_context() == {}

    def test_the_context_is_cleared_when_the_request_raises(self) -> None:
        def view(request: HttpRequest) -> HttpResponse:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            _id_middleware(view)(_api_request(request_id="doomed"))

        assert current_log_context() == {}

    def test_the_request_is_bound_so_the_user_can_be_resolved_later(self) -> None:
        seen: dict[str, Any] = {}

        def view(request: HttpRequest) -> HttpResponse:
            seen.update(current_log_context())
            return HttpResponse("ok")

        request = _api_request()
        _id_middleware(view)(request)

        # Authentication has not run when the middleware binds the context, so
        # the user id is derived from the request at emit time instead.
        assert seen["request"] is request


class TestAccessLog:
    @staticmethod
    def _capture(caplog: pytest.LogCaptureFixture) -> None:
        """Make this logger's records reach caplog.

        The project configures the "shared" logger with propagate=False, so its
        records never reach the root handler caplog installs.
        """
        caplog.set_level(logging.INFO, logger="shared.infrastructure.middleware")
        logging.getLogger("shared").propagate = True

    def test_writes_one_line_per_request(
        self, settings: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        settings.REQUEST_LOGGING = True
        self._capture(caplog)

        _id_middleware()(_api_request(path="/api/v1/tasks/", method="POST"))

        records = [
            record
            for record in caplog.records
            if record.getMessage() == "POST /api/v1/tasks/ 200"
        ]
        assert len(records) == 1
        # Attached through logging's extra= keyword, which mypy cannot see.
        assert records[0].status_code == 200  # type: ignore[attr-defined]
        assert records[0].duration_ms >= 0  # type: ignore[attr-defined]

    def test_logs_the_failure_status_of_a_server_error(
        self, settings: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        settings.REQUEST_LOGGING = True
        self._capture(caplog)
        middleware = _id_middleware(lambda request: HttpResponse("", status=503))

        response = middleware(_api_request())

        assert response.status_code == 503
        assert any(
            record.getMessage() == "GET /api/v1/tasks/ 503" for record in caplog.records
        )

    def test_never_logs_the_query_string_or_a_header(
        self, settings: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        # A query string carries identifiers and a header carries the JWT; a log
        # store outlives the request, so neither belongs in it.
        settings.REQUEST_LOGGING = True
        self._capture(caplog)
        request = _api_request(path="/api/v1/tasks/")
        request.META["QUERY_STRING"] = "token=secret"
        request.META["HTTP_AUTHORIZATION"] = "Bearer secret-token"

        _id_middleware()(request)

        rendered = " ".join(record.getMessage() for record in caplog.records)
        assert "secret" not in rendered

    def test_is_off_by_default_in_the_test_environment(self) -> None:
        # Django constructs the middleware without arguments, so the deployment's
        # REQUEST_LOGGING setting is read in the constructor.
        assert _id_middleware().log_requests is False

    def test_can_be_turned_off_through_settings(
        self, settings: Any, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._capture(caplog)
        settings.REQUEST_LOGGING = False
        middleware = _id_middleware()

        response = middleware(_api_request())

        assert middleware.log_requests is False
        assert response[REQUEST_ID_HEADER], "the id is published either way"
        assert not caplog.records, "but no access line is written"

    def test_a_middleware_failure_is_logged_before_it_propagates(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        self._capture(caplog)

        def view(request: HttpRequest) -> HttpResponse:
            raise RuntimeError("boom")

        # Django converts a view's exception into a 500 below this middleware,
        # so reaching the raise here means the failure was in middleware: the
        # record is the only trace that will exist.
        with pytest.raises(RuntimeError):
            _id_middleware(view)(_api_request())

        assert any(
            record.exc_info is not None for record in caplog.records
        ), "an unhandled middleware failure must leave a record behind"


class TestSanitizeRequestId:
    def test_none_and_blank_return_none(self) -> None:
        assert sanitize_request_id(None) is None
        assert sanitize_request_id("   ") is None
        assert sanitize_request_id("/") is None

    def test_a_clean_id_is_returned_unchanged(self) -> None:
        assert sanitize_request_id("  trace-1.A_b ") == "trace-1.A_b"

    def test_new_request_id_is_a_uuid(self) -> None:
        assert new_request_id() != new_request_id()
