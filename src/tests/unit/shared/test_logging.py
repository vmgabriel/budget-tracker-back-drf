"""Unit tests for the shared structured logging adapter."""

from __future__ import annotations

import json
import logging
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from shared.infrastructure.logging import (
    DEFAULT_SUPPRESSED_LOGGERS,
    JsonLogFormatter,
    bind_log_context,
    build_logging_config,
    current_log_context,
    log_context,
    reset_log_context,
)

pytestmark = pytest.mark.unit


def _record(
    msg: str = "hello",
    *,
    level: int = logging.INFO,
    logger_name: str = "apps.tasks",
    args: tuple[Any, ...] = (),
    exc_info: Any = None,
) -> logging.LogRecord:
    """Build a LogRecord the way the logging machinery would."""
    return logging.LogRecord(
        name=logger_name,
        level=level,
        pathname=__file__,
        lineno=42,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )


def _format(record: logging.LogRecord) -> dict[str, Any]:
    """Format a record and parse the result back into a dictionary."""
    return _format_line(record)


def _format_line(record: logging.LogRecord) -> dict[str, Any]:
    """Format a record, asserting the one-record-per-line contract first."""
    line = JsonLogFormatter().format(record)
    assert "\n" not in line, "one record must never span multiple lines"
    parsed: dict[str, Any] = json.loads(line)
    return parsed


class TestJsonFormatter:
    def test_emits_the_mandatory_fields(self) -> None:
        payload = _format(_record("dumped"))

        assert payload["message"] == "dumped"
        assert payload["level"] == "INFO"
        assert payload["logger"] == "apps.tasks"
        assert payload["service"] == "life-utility"
        # UTC, ISO-8601, millisecond precision, Z suffix.
        assert payload["timestamp"].endswith("Z")
        assert "T" in payload["timestamp"]

    def test_renders_the_level_name_not_the_number(self) -> None:
        assert _format(_record(level=logging.ERROR))["level"] == "ERROR"

    def test_applies_message_arguments(self) -> None:
        payload = _format(_record("user %s moved %s", args=("7", "3 files")))

        assert payload["message"] == "user 7 moved 3 files"

    def test_carries_the_ambient_request_context(self) -> None:
        with log_context(
            request_id="abc-123",
            user_id="42",
            path="/api/v1/tasks/",
            method="POST",
        ):
            payload = _format(_record("handled"))

        assert payload["request_id"] == "abc-123"
        assert payload["user_id"] == "42"
        assert payload["path"] == "/api/v1/tasks/"
        assert payload["method"] == "POST"

    def test_omits_context_fields_that_are_not_bound(self) -> None:
        with log_context(request_id="abc-123"):
            payload = _format(_record())

        assert payload["request_id"] == "abc-123"
        assert "user_id" not in payload
        assert "path" not in payload

    def test_resolves_the_user_from_a_bound_request(self) -> None:
        # The middleware binds the request before authentication runs, so the
        # user is read at emit time, by which point a view has authenticated.
        request = SimpleNamespace(user=SimpleNamespace(pk=42, is_authenticated=True))
        with log_context(request=request):
            payload = _format(_record())

        assert payload["user_id"] == "42"
        assert "request" not in payload, "the request object is not serialized"

    def test_an_anonymous_request_yields_no_user_id(self) -> None:
        request = SimpleNamespace(user=SimpleNamespace(pk=None, is_authenticated=False))
        with log_context(request=request):
            payload = _format(_record())

        assert "user_id" not in payload

    def test_a_request_without_a_user_is_tolerated(self) -> None:
        # Authentication middleware sits below this one, so request.user may not
        # exist yet when something very early logs.
        with log_context(request=object()):
            payload = _format(_record())

        assert "user_id" not in payload

    def test_an_explicit_user_id_wins_over_the_bound_request(self) -> None:
        request = SimpleNamespace(user=SimpleNamespace(pk=1, is_authenticated=True))
        with log_context(request=request, user_id="99"):
            payload = _format(_record())

        assert payload["user_id"] == "99"

    def test_serializes_caller_supplied_extras(self) -> None:
        record = _record()
        record.status_code = 503
        record.duration_ms = 12.5

        payload = _format(record)

        assert payload["status_code"] == 503
        assert payload["duration_ms"] == 12.5

    def test_does_not_serialize_a_request_object(self) -> None:
        # Django attaches the WSGIRequest to its error records, and its repr
        # contains the query string.
        record = _record(level=logging.ERROR)
        record.request = "/api/v1/tasks/?token=secret"

        payload = _format(record)

        assert "request" not in payload

    def test_keeps_a_non_json_extra_as_a_string_rather_than_dropping_the_line(
        self,
    ) -> None:
        record = _record()
        record.broken = object()

        payload = _format(record)

        assert isinstance(payload["broken"], str)

    def test_does_not_serialize_record_builtins(self) -> None:
        payload = _format(_record())

        assert "pathname" not in payload
        assert "lineno" not in payload

    def test_renders_an_exception_on_the_same_line(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            record = _record("failed", level=logging.ERROR, exc_info=sys.exc_info())

        line = JsonLogFormatter().format(record)

        # The traceback is inherently multi-line; json.dumps escapes its
        # newlines, so the encoded record is still the single line a shipper
        # can parse, and the traceback survives intact once parsed.
        assert "\n" not in line
        assert "ValueError: boom" in line
        assert "\n" in json.loads(line)["exception"]


class TestLogContext:
    def test_context_is_empty_by_default(self) -> None:
        assert current_log_context() == {}

    def test_bind_merges_into_the_existing_context(self) -> None:
        token = bind_log_context(request_id="one")
        try:
            bind_log_context(user_id="2")
            assert current_log_context() == {"request_id": "one", "user_id": "2"}
        finally:
            reset_log_context(token)

    def test_a_none_value_clears_the_field(self) -> None:
        token = bind_log_context(request_id="one", user_id="2")
        try:
            bind_log_context(user_id=None)
            assert current_log_context() == {"request_id": "one"}
        finally:
            reset_log_context(token)

    def test_the_context_is_restored_when_the_block_raises(self) -> None:
        with pytest.raises(ValueError), log_context(request_id="boom"):
            raise ValueError("boom")

        # A reused worker thread must not inherit the failed request's id.
        assert current_log_context() == {}

    def test_nested_blocks_restore_the_outer_context(self) -> None:
        with log_context(request_id="outer"):
            with log_context(request_id="inner"):
                assert current_log_context()["request_id"] == "inner"
            assert current_log_context()["request_id"] == "outer"

    def test_the_returned_snapshot_cannot_mutate_the_binding(self) -> None:
        with log_context(request_id="one"):
            snapshot: dict[str, Any] = dict(current_log_context())
            snapshot["request_id"] = "tampered"

            assert current_log_context()["request_id"] == "one"


class TestBuildLoggingConfig:
    def test_development_shape_uses_the_readable_format(self) -> None:
        config = build_logging_config()

        assert config["handlers"]["console"]["formatter"] == "standard"
        # The stream is resolved when the handler is constructed, not here, so
        # Gunicorn's own redirection still applies.
        assert "stream" not in config["handlers"]["console"]

    def test_production_shape_uses_the_json_formatter_on_the_console(self) -> None:
        config = build_logging_config(json_output=True)

        assert (
            config["handlers"]["console"]["formatter"] == "json"
        ), "container logs must be the format a shipper can parse"
        assert config["formatters"]["json"]["()"] == (
            "shared.infrastructure.logging.JsonLogFormatter"
        )

    def test_no_file_handler_unless_a_path_is_given(self) -> None:
        assert "file" not in build_logging_config()["handlers"]

        config = build_logging_config(file_path="/var/log/app.log")

        assert config["handlers"]["file"]["class"] == (
            "logging.handlers.RotatingFileHandler"
        )
        assert config["loggers"]["django"]["handlers"] == [
            "console",
            "file",
        ], "the file handler joins the console, it does not replace it"

    def test_root_and_django_share_the_level(self) -> None:
        config = build_logging_config(level="WARNING")

        assert config["root"]["level"] == "WARNING"
        assert config["loggers"]["django"]["level"] == "WARNING"

    def test_celery_falls_back_to_the_application_level(self) -> None:
        assert build_logging_config(level="DEBUG")["loggers"]["celery"]["level"] == (
            "DEBUG"
        )
        assert (
            build_logging_config(level="DEBUG", celery_level="WARNING")["loggers"][
                "celery"
            ]["level"]
            == "WARNING"
        )

    def test_application_and_shared_loggers_are_configured(self) -> None:
        loggers = build_logging_config()["loggers"]

        assert "apps" in loggers
        assert "shared" in loggers

    def test_query_logging_is_debug_only_when_asked_for(self) -> None:
        assert build_logging_config()["loggers"]["django.db.backends"]["level"] == (
            "WARNING"
        )
        assert (
            build_logging_config(query_logging=True)["loggers"]["django.db.backends"][
                "level"
            ]
            == "DEBUG"
        )

    def test_noise_is_raised_to_error_not_disabled(self) -> None:
        loggers = build_logging_config()["loggers"]

        for name in DEFAULT_SUPPRESSED_LOGGERS:
            assert (
                loggers[name]["level"] == "ERROR"
            ), f"{name} must stay visible at ERROR, not be silenced"

    def test_suppressed_loggers_can_be_overridden(self) -> None:
        loggers = build_logging_config(suppressed_loggers=())["loggers"]

        assert "django.security.DisallowedHost" not in loggers

    def test_never_disables_loggers_configured_before_django(self) -> None:
        assert build_logging_config()["disable_existing_loggers"] is False
