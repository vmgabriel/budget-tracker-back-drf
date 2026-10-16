"""Structured logging for the shared kernel.

Two things live here:

* :class:`JsonLogFormatter`, which turns a :class:`logging.LogRecord` into one
  JSON object per line, so a log shipper can index it without a grok pattern.
* :func:`build_logging_config`, which assembles the Django ``LOGGING``
  dictionary from a handful of environment-driven values.

The ambient request context (request id, user, path, method) is held in a
:class:`~contextvars.ContextVar` rather than threaded through every call site.
A Celery task or a use case that logs deep inside a request therefore carries
the same identifiers as the view that started it, with no signature changes
anywhere. The variable, not a global, is what makes that correct: a
``ContextVar`` is isolated per thread and per asyncio task, so two Gunicorn
workers — and two requests inside one worker — never see each other's ids.

This module imports nothing outside the standard library. It is loaded by the
settings module during Django's import of ``LOGGING``, so it must not import
Django, and keeping it stdlib-only means it is also unit-testable without a
configured settings module.

The file is deliberately named ``logging`` because it *is* the project's
logging adapter. Absolute imports (PEP 328) mean ``import logging`` from any
sibling module still resolves to the standard library, not to this file.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

#: Ambient fields promoted to first-class keys in every JSON line. They are
#: emitted before any caller-supplied ``extra`` so that a log entry always has
#: the same identifying prefix, whatever the caller attached.
CONTEXT_FIELDS = ("request_id", "user_id", "path", "method")

#: Attributes every ``LogRecord`` already carries. Anything else on the record
#: was passed through ``extra=`` by the caller and is worth serializing.
_STANDARD_RECORD_ATTRIBUTES = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)

#: Loggers that are pure noise at their normal level. Django emits a record
#: here for every request that fails the host or origin allowlist, which on an
#: internet-facing deployment is a scanner probing constantly; at ERROR level
#: the signal survives a typo in ``ALLOWED_HOSTS`` without burying the log.
DEFAULT_SUPPRESSED_LOGGERS: tuple[str, ...] = (
    "django.security.DisallowedHost",
    "django.security.InsecureRequestHeader",
    "django.security.SuspiciousOperation",
    "django.utils.autotranslate",
    # The WSGI request log duplicates the access line the web server already
    # writes, with no request id attached.
    "django.server",
)

_current_context: ContextVar[Mapping[str, Any] | None] = ContextVar(
    "shared_infrastructure_log_context",
    default=None,
)

#: Record attributes that are never serialized, even when a caller passed them
#: through ``extra``. Django attaches the whole ``WSGIRequest`` to its error
#: records, and its repr contains the full request line including the query
#: string — which is exactly what must not end up in a log store.
_EXCLUDED_RECORD_KEYS = frozenset({"request"})


def current_log_context() -> Mapping[str, Any]:
    """Return the ambient log context, empty when nothing is bound.

    Returns:
        An immutable snapshot of the bound fields. Copying on read means a
        caller cannot mutate the context another thread is logging from.
    """
    context = _current_context.get()
    return dict(context) if context else {}


def bind_log_context(**fields: Any) -> Token[Mapping[str, Any] | None]:
    """Merge ``fields`` into the ambient context and return a reset token.

    Args:
        **fields: Ambient values such as ``request_id`` or ``user_id``. A value
            of ``None`` *clears* that field rather than logging a null: an
            anonymous request must not inherit the previous request's user id,
            and "absent" is more useful to a log query than an explicit null.

    Returns:
        A token for :func:`reset_log_context`. Returning it rather than hiding
        it keeps nesting explicit and keeps a failed reset from silencing a
        caller's context for the rest of the thread's life.
    """
    merged = dict(current_log_context())
    for key, value in fields.items():
        if value is None:
            merged.pop(key, None)
        else:
            merged[key] = value
    return _current_context.set(merged)


def reset_log_context(token: Token[Mapping[str, Any] | None]) -> None:
    """Restore the ambient context to what it was before ``token``."""
    _current_context.reset(token)


@contextmanager
def log_context(**fields: Any) -> Iterator[None]:
    """Bind ``fields`` for the duration of the block.

    The context is restored even when the block raises, which is what keeps one
    failed request from stamping its request id onto the next request served by
    the same worker thread.
    """
    token = bind_log_context(**fields)
    try:
        yield
    finally:
        reset_log_context(token)


def _iso_timestamp(created: float) -> str:
    """Render a record creation time as UTC ISO-8601 with a ``Z`` suffix.

    ``datetime.fromtimestamp`` in UTC rather than local time: log aggregation
    is timezone-blind, and a container running in UTC while the operator's
    laptop is not would otherwise silently shift every line.
    """
    return (
        datetime.fromtimestamp(created, tz=UTC)
        .isoformat(
            timespec="milliseconds",
        )
        .replace("+00:00", "Z")
    )


def _resolve_user_id(request: Any) -> str | None:
    """Return the authenticated user's id from a bound request, if any.

    Duck-typed on purpose: this module must not import Django, and it must not
    touch ``request.user`` on an anonymous request, because the object is lazy
    and reading it creates a session row per anonymous call. The
    ``is_authenticated`` check is what prevents that.
    """
    if request is None:
        return None
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    pk = getattr(user, "pk", None)
    return None if pk is None else str(pk)


def _jsonable(value: Any) -> Any:
    """Coerce a ``extra`` value into something ``json.dumps`` accepts.

    Callers attach counts, durations, and occasionally an exception object. A
    formatter that raised on an unexpected type would lose the whole log line,
    which is the opposite of what observability is for, so unknown objects are
    stringified instead.
    """
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


class JsonLogFormatter(logging.Formatter):
    """Render a record as a single JSON object on one line.

    Every line carries ``timestamp``, ``level``, ``logger``, ``service``, and
    ``message``. The ambient context fields follow when they are set, then any
    caller-supplied ``extra``, then ``exception`` for a traceback. One line per
    record is the whole point: a multi-line traceback in a JSON log is a
    parsing problem for everything downstream.
    """

    def __init__(self, *, service: str = "life-utility") -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        """Return ``record`` as a JSON object.

        Args:
            record: The record to serialize.

        Returns:
            A single-line JSON document, without the trailing newline the
            handler adds.
        """
        payload: dict[str, Any] = {
            "timestamp": _iso_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "service": self.service,
            "message": record.getMessage(),
        }

        context = current_log_context()
        for key in CONTEXT_FIELDS:
            value = context.get(key)
            if value is not None:
                payload[key] = value

        # The user is resolved here rather than bound up front: the middleware
        # runs before authentication, so at bind time there is no user yet, but
        # by the time a view logs, `request.user` has been populated by the
        # session or by JWT authentication.
        user_id = _resolve_user_id(context.get("request"))
        if user_id is not None:
            payload.setdefault("user_id", user_id)

        for key, value in vars(record).items():
            if key in _STANDARD_RECORD_ATTRIBUTES or key in payload:
                continue
            if key in _EXCLUDED_RECORD_KEYS or value is None:
                continue
            payload[key] = _jsonable(value)

        # Context fields bound by the caller but not in CONTEXT_FIELDS are
        # still useful (a task id, a queue name), so they are kept as extras.
        # The bound request object is not: it is a whole object graph, and the
        # user id derived from it is already in the payload.
        for key, value in context.items():
            if key not in payload and key != "request" and value is not None:
                payload[key] = _jsonable(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def build_logging_config(
    *,
    level: str = "INFO",
    celery_level: str | None = None,
    json_output: bool = False,
    file_path: str | None = None,
    service: str = "life-utility",
    query_logging: bool = False,
    suppressed_loggers: Sequence[str] = DEFAULT_SUPPRESSED_LOGGERS,
) -> dict[str, Any]:
    """Build the Django ``LOGGING`` dictionary.

    Kept as a plain function over plain values so it can be unit-tested
    without Django, and so the settings module stays a statement of intent
    ("JSON in production") rather than a hand-maintained dictionary.

    Args:
        level: Root and Django level. Defaults to ``INFO``.
        celery_level: Celery's own level; defaults to ``level`` when omitted,
            which is right for nearly every deployment.
        json_output: Emit one JSON object per line instead of the readable
            development format. Production wants this.
        file_path: Optional local file for a second, rotating-by-rotation
            copy. Empty or ``None`` means stdout only, which is what a
            containerized deployment wants, because a file inside the container
            is lost with the container and invisible to `docker compose logs`.
        service: Value written to every line's ``service`` field, so logs from
            the web process, the worker, and Beat can be told apart when they
            share a sink.
        query_logging: Log every SQL statement. Off by default everywhere,
            including production: the statements contain parameter values.
        suppressed_loggers: Loggers whose records are raised to ``ERROR``.

    Returns:
        A configuration dictionary shaped for ``django.utils.log`.
    """
    formatter_name = "json" if json_output else "standard"

    formatters: dict[str, Any] = {
        "standard": {
            # Readable in a terminal, which is the only place development
            # looks at logs.
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
        "json": {"()": "shared.infrastructure.logging.JsonLogFormatter"},
    }

    handlers: dict[str, Any] = {
        "console": {
            # No explicit stream: the handler picks up whatever sys.stderr is at
            # configuration time, which is after Gunicorn has applied its own
            # redirection. Binding sys.stdout here instead would capture the
            # stream too early and defeat that.
            "class": "logging.StreamHandler",
            "formatter": formatter_name,
        },
    }

    if file_path:
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": file_path,
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "formatter": formatter_name,
        }

    active_handlers = ["console", "file"] if file_path else ["console"]

    loggers: dict[str, Any] = {
        "django": {
            "handlers": active_handlers,
            "level": level,
            "propagate": False,
        },
        # Split out explicitly: this is the logger a 4xx or 5xx is reported on,
        # so an operator can raise or lower it without touching everything
        # Django logs.
        "django.request": {
            "handlers": active_handlers,
            "level": level,
            "propagate": False,
        },
        # Query logging is opt-in. At DEBUG this logger emits one line per
        # statement, which is useful with DJANGO_LOG_QUERIES and unusable
        # otherwise.
        "django.db.backends": {
            "handlers": active_handlers,
            "level": "DEBUG" if query_logging else "WARNING",
            "propagate": False,
        },
        # The application's own bounded contexts. Anything a context logs
        # without configuring its own handler lands here.
        "apps": {
            "handlers": active_handlers,
            "level": level,
            "propagate": False,
        },
        "shared": {
            "handlers": active_handlers,
            "level": level,
            "propagate": False,
        },
        "celery": {
            "handlers": active_handlers,
            "level": celery_level or level,
            "propagate": False,
        },
    }

    for name in suppressed_loggers:
        # ERROR, not "disabled": the setting silences routine noise while a
        # genuine misconfiguration (a host that should be allowed, a header
        # that should be trusted) still surfaces once.
        loggers[name] = {
            "handlers": active_handlers,
            "level": "ERROR",
            "propagate": False,
        }

    return {
        "version": 1,
        # Never disable existing loggers: a library that configured its own
        # handler before Django configured logging must keep it.
        "disable_existing_loggers": False,
        "formatters": formatters,
        "handlers": handlers,
        "loggers": loggers,
        "root": {
            "handlers": active_handlers,
            "level": level,
        },
    }
