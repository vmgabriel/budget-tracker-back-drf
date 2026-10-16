"""Request correlation and structured logging, over real HTTP.

The unit tests in ``tests/unit/shared`` cover the middleware and the formatter
in isolation. These go through the full Django stack, because the properties
that matter operationally only exist there: the response header really reaches
the client, the middleware really is the outermost one, and a view's own log
record really carries the same correlation id as the access line.
"""

import json
import logging

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from shared.infrastructure.logging import JsonLogFormatter, log_context

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

#: The middleware logs here. Its records are configured not to propagate, so
#: the test attaches itself to that logger instead of the root one.
ACCESS_LOGGER = "shared.infrastructure.middleware"


class _CapturingJsonHandler(logging.Handler):
    """Format each record as JSON and keep the lines.

    The ambient request context (and therefore ``request_id``) is injected by
    the formatter at emit time, while the middleware's ``log_context`` is still
    bound. caplog keeps raw records and would be formatted long after that block
    has exited, so it cannot observe the context: a handler that formats during
    the request can.
    """

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []
        self.formatter = JsonLogFormatter()

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture(autouse=True)
def _capture_shared_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Route the shared logger's records to caplog.

    The project configures the "shared" logger with propagate=False, so its
    records never reach the root handler caplog installs. Each test reads
    ``caplog.records`` directly rather than receiving the list up front, because
    pytest resets the capture around the call phase; holding the list in a
    fixture would hand the test a stale, empty one.
    """
    caplog.set_level(logging.INFO, logger=ACCESS_LOGGER)
    logging.getLogger("shared").propagate = True


class TestResponseHeader:
    def test_every_response_carries_a_request_id(self) -> None:
        response = APIClient().get(reverse("liveness"))

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]

    def test_an_id_sent_by_the_caller_is_returned_unchanged(self) -> None:
        # A gateway or a front end that started the trace must be able to keep
        # quoting the same id back to the operator.
        response = APIClient().get(
            reverse("liveness"), headers={"X-Request-ID": "edge-trace-1"}
        )

        assert response.headers["X-Request-ID"] == "edge-trace-1"

    def test_an_api_error_response_carries_one_too(self) -> None:
        response = APIClient().get("/api/v1/does-not-exist/")

        assert response.status_code == 404
        assert response.headers["X-Request-ID"]

    def test_two_requests_get_different_ids(self) -> None:
        client = APIClient()

        first = client.get(reverse("liveness"))["X-Request-ID"]
        second = client.get(reverse("liveness"))["X-Request-ID"]

        assert first != second


class TestAccessLog:
    @override_settings(REQUEST_LOGGING=True)
    def test_the_access_line_shares_the_response_request_id(self) -> None:
        # The middleware reads the setting when it is constructed, and the test
        # client builds the chain per client instance, so the override applies.
        logger = logging.getLogger(ACCESS_LOGGER)
        handler = _CapturingJsonHandler()
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        try:
            response = APIClient().get(reverse("liveness"))
        finally:
            logger.removeHandler(handler)

        access = [
            json.loads(line)
            for line in handler.lines
            if json.loads(line)["message"].startswith("GET ")
        ]
        assert len(access) == 1
        assert access[0]["request_id"] == response["X-Request-ID"]
        assert access[0]["status_code"] == 200

    @override_settings(REQUEST_LOGGING=True)
    def test_a_rejected_request_is_logged_with_its_status(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        response = APIClient().get("/api/v1/does-not-exist/")

        assert response.status_code == 404
        assert any(
            getattr(record, "status_code", None) == 404 for record in caplog.records
        )


class TestStructuredOutput:
    def test_a_record_formats_as_one_json_line_carrying_the_context(self) -> None:
        record = logging.LogRecord(
            name="apps.tasks",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="plan generated",
            args=(),
            exc_info=None,
        )
        with log_context(request_id="trace-9", path="/api/v1/plans/", method="POST"):
            line = JsonLogFormatter().format(record)

        payload = json.loads(line)
        assert "\n" not in line
        assert payload["request_id"] == "trace-9"
        assert payload["path"] == "/api/v1/plans/"
        assert payload["method"] == "POST"
        assert payload["message"] == "plan generated"
        assert payload["timestamp"].endswith("Z")
