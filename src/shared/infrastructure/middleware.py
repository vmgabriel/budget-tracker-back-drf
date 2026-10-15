"""HTTP middleware shared by every bounded context.

Django's :class:`~django.middleware.security.SecurityMiddleware` already emits
``X-Content-Type-Options`` and ``X-Frame-Options`` from settings, and that stays
the single source of truth for those two headers. This middleware adds the
policy headers that settings express awkwardly, and it applies them uniformly:
the API responses, the OpenAPI schema, and the Django admin served by the same
process all get the same headers.

It only fills in headers that are absent, so it composes with Django's own
middleware and with a reverse proxy that adds its own headers, instead of
fighting them over the same response.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from django.conf import settings
from django.http import HttpRequest, HttpResponse

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
