"""HTTP middleware shared by every bounded context.

Two middlewares live here, both deliberately small and both header- or
context-level rather than business-level.

:class:`SecurityHeadersMiddleware` adds the policy headers that settings
express awkwardly. Django's
:class:`~django.middleware.security.SecurityMiddleware` already emits
``X-Content-Type-Options`` and ``X-Frame-Options`` from settings, and that
stays the single source of truth for those two headers. It only fills in
headers that are absent, so it composes with Django's own middleware and with
a reverse proxy that adds its own headers, instead of fighting them over the
same response.

:class:`RequestIdMiddleware` gives every request an identifier, publishes it on
the response, and binds it to the logging context so every record emitted
while handling that request — including from Celery-adjacent code, a
repository, or a serializer — can be traced back to it.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Callable, Mapping

from django.conf import settings
from django.http import HttpRequest, HttpResponse

from shared.infrastructure.logging import log_context

logger = logging.getLogger(__name__)

#: Header carrying the correlation id in both directions: an inbound request may
#: arrive with one from an upstream proxy or gateway, and every response returns
#: it so a client can quote it in a bug report.
REQUEST_ID_HEADER = "X-Request-ID"

#: Upper bound on an accepted inbound id. An unbounded header is an
#: unbounded log line, and a log aggregator with a per-field size limit drops
#: the whole record, losing the id that was supposed to make it findable.
MAX_REQUEST_ID_LENGTH = 64

#: Characters allowed in an inbound id. Anything else is replaced rather than
#: rejected: an id is an opaque correlation token, and sanitizing it keeps a
#: hostile header from injecting newlines or terminal escape sequences into the
#: log stream.
_DISALLOWED_REQUEST_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]")

DEFAULT_X_FRAME_OPTIONS = "DENY"
DEFAULT_CONTENT_TYPE_OPTIONS = "nosniff"

#: The default the Referrer-Policy header carries. ``strict-origin-when-cross-
#: origin`` keeps the full referrer for same-origin navigation and drops the
#: path on cross-origin requests, which is where referrer URLs can leak
#: identifiers.
DEFAULT_REFERRER_POLICY = "strict-origin-when-cross-origin"

#: The browser APIs this API never uses. Denying them means an injected script
#: cannot raise a camera, microphone, or geolocation prompt that looks like it
#: came from the application. ``fullscreen=(self)`` is left alone because the
#: admin is usable without it and it is harmless.
DEFAULT_PERMISSIONS_POLICY = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
    "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), midi=(), payment=(), usb=()"
)

#: Default header set. A deployment can override or extend it through
#: ``settings.SECURITY_HEADERS``; an empty value removes a header, which is how
#: a front end that needs a relaxed policy opts out.
DEFAULT_SECURITY_HEADERS: Mapping[str, str] = {
    "X-Content-Type-Options": DEFAULT_CONTENT_TYPE_OPTIONS,
    "X-Frame-Options": DEFAULT_X_FRAME_OPTIONS,
    "Referrer-Policy": DEFAULT_REFERRER_POLICY,
    "Permissions-Policy": DEFAULT_PERMISSIONS_POLICY,
}


class SecurityHeadersMiddleware:
    """Attach hardening response headers that Django settings do not cover.

    Deliberately no Content-Security-Policy by default: this process also
    serves the Django admin, whose templates would need per-page exceptions.
    Add one through ``SECURITY_HEADERS`` once the admin is fronted separately.
    """

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponse],
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.get_response = get_response
        if headers is not None:
            self.headers = headers
            return
        # Django instantiates middleware with the get_response callable alone,
        # so the deployment's configuration is read here rather than passed in.
        # getattr keeps the middleware usable outside a configured Django (in
        # unit tests that build it directly).
        self.headers = getattr(settings, "SECURITY_HEADERS", DEFAULT_SECURITY_HEADERS)

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Add the security headers to every response, including error paths."""
        response = self.get_response(request)
        for name, value in self.headers.items():
            if value and not response.has_header(name):
                response[name] = value
        return response


def new_request_id() -> str:
    """Return a fresh correlation id."""
    return str(uuid.uuid4())


def sanitize_request_id(raw: str | None) -> str | None:
    """Normalize an inbound request id, or return ``None`` if unusable.

    An id supplied by a client is untrusted input that is about to be written
    into a log line and echoed back in a header. Trimming, stripping disallowed
    characters, and bounding its length makes that safe without rejecting a
    legitimate upstream id over a stray character. An id that sanitizes down to
    nothing is treated as absent, and a new one is generated.

    Args:
        raw: The inbound header value, if the request carried one.

    Returns:
        A log-safe identifier, or ``None`` when the caller should mint one.
    """
    if raw is None:
        return None
    cleaned = _DISALLOWED_REQUEST_ID_CHARS.sub("-", raw.strip())[:MAX_REQUEST_ID_LENGTH]
    cleaned = cleaned.strip("-")
    return cleaned or None


class RequestIdMiddleware:
    """Correlate every log record emitted while handling one request.

    The id is taken from ``X-Request-ID`` when the caller supplies a usable
    one, so a trace started at an edge proxy survives into the application, and
    generated otherwise. It is bound to the ambient logging context for the
    duration of the call and returned on the response.

    The binding is context-scoped and released even when the request raises,
    because a worker thread is reused: an id left behind would tag the next
    request served by that thread with the previous one's identifier, which is
    worse than having no id at all.

    The middleware also writes one access line per request. Gunicorn's own
    access log covers the request line and duration, but it is emitted by the
    server process, which never sees the correlation id — so the two together
    cannot be joined. Set ``DJANGO_LOG_REQUESTS=false`` to silence this one and
    rely on the server's log alone.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        # Read through settings so the middleware is constructible without a
        # configured Django, which is what the unit tests do. The default is
        # "log": an access line is the cheapest observability available.
        self.log_requests: bool = (
            bool(getattr(settings, "REQUEST_LOGGING", True))
            if settings.configured
            else True
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Bind the request context, run the rest of the stack, publish the id."""
        request_id = sanitize_request_id(request.headers.get(REQUEST_ID_HEADER))
        if request_id is None:
            request_id = new_request_id()
        request.request_id = request_id  # type: ignore[attr-defined]

        started = time.monotonic()
        # The request itself is bound as well as its parts: authentication has
        # not run yet at this point, so the user id is resolved lazily by the
        # formatter from whatever request.user holds at emit time.
        with log_context(
            request_id=request_id,
            path=request.path,
            method=request.method,
            request=request,
        ):
            try:
                response = self.get_response(request)
            except Exception:
                # Django converts a view's exception into a 500 response below
                # this point, so reaching here means the failure was in
                # middleware rather than in a handler. Log it anyway: an
                # unhandled middleware failure that produced no record at all
                # is the hardest kind to diagnose.
                logger.exception(
                    "middleware_failure",
                    extra={"duration_ms": self._elapsed_ms(started)},
                )
                raise

            self._log_request(request, response, self._elapsed_ms(started))

            response[REQUEST_ID_HEADER] = request_id
            return response

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        """Return the milliseconds elapsed since a ``time.monotonic()`` stamp."""
        return round((time.monotonic() - started) * 1000, 2)

    def _log_request(
        self,
        request: HttpRequest,
        response: HttpResponse,
        duration_ms: float,
    ) -> None:
        """Emit the per-request access line, when it is enabled.

        The status code, method, path, and duration only. Deliberately not the
        query string or any header: a query string carries identifiers and a
        header carries the JWT, and neither belongs in a log store that is
        usually retained for far longer than the request itself.
        """
        if not self.log_requests:
            return
        logger.info(
            "%s %s %s",
            request.method,
            request.path,
            response.status_code,
            extra={"status_code": response.status_code, "duration_ms": duration_ms},
        )
