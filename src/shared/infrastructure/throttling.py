"""Request throttles shared by every bounded context.

Rate limiting belongs in this shared infrastructure layer rather than in one
bounded context: the login and registration endpoints live in ``users``, but
the same policy has to apply to any future unauthenticated endpoint, and the
rates themselves are configuration.

The counters live in Django's default cache. That is process-local by default,
which is enough for a single host but not for several replicas behind a load
balancer, where each replica would allow its own share of the budget. Point
``CACHES["default"]`` at Redis (already required for Celery) to make the limits
global; the classes here do not care which backend answers.
"""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from rest_framework.throttling import SimpleRateThrottle


class ScopedRateThrottle(SimpleRateThrottle):
    """Base class for a throttle whose rate is looked up by scope name.

    DRF's :class:`~rest_framework.throttling.SimpleRateThrottle` is abstract
    until a subclass names its ``scope``; this class adds the ability to
    declare the scope in a settings-driven mapping instead, so the same class
    can serve several rates without one class per limit.
    """

    def __init__(self, scope: str | None = None) -> None:
        # DRF declares `scope = None` without an annotation, so mypy infers a
        # literal None type and rejects the string assignment; the instance
        # attribute is set through the constructor argument instead.
        selected = scope or type(self).scope
        if not selected:
            raise ValueError(f"{type(self).__name__} requires a throttle scope.")
        self.scope = selected  # type: ignore[assignment]
        super().__init__()

    def get_cache_key(
        self, request: HttpRequest, view: Any
    ) -> str | None:  # noqa: ANN401
        """Key the counter by scope and client identity.

        The login and registration views are unauthenticated, so DRF keys on
        the client IP address taken from ``X-Forwarded-For`` when the proxy
        count (``REST_FRAMEWORK["NUM_PROXIES"]``) says a proxy is in front.
        That count is the security-relevant part: with it unset, the immediate
        peer's address is used, which behind a reverse proxy is the proxy's, so
        every client would share one bucket and a single noisy caller could lock
        out everyone.
        """
        if request.user and request.user.is_authenticated:
            # Authenticated traffic is throttled per account rather than per IP
            # so a shared NAT (a household, an office) does not collide.
            ident = f"user:{request.user.pk}"
        else:
            ident = f"ip:{self.get_ident(request)}"
        return self.cache_format % {"scope": self.scope, "ident": ident}


class LoginRateThrottle(ScopedRateThrottle):
    """Throttle token issuance to slow credential stuffing.

    Ten attempts a minute is generous for an interactive login form while still
    making a password-spraying run across thousands of accounts impractical.
    The rate is the ``login`` entry in ``REST_FRAMEWORK['DEFAULT_THROTTLE_
    RATES']``, so it is configurable without a code change.
    """

    scope = "login"  # type: ignore[assignment]


class RegisterRateThrottle(ScopedRateThrottle):
    """Throttle account creation to stop mass sign-ups from one address.

    Five an hour is the floor, not the ceiling: a shared NAT, a school, or an
    office can legitimately exhaust it. Rotate the ``register`` rate upward if
    real users report being blocked.
    """

    scope = "register"  # type: ignore[assignment]
