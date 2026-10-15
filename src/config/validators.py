"""Startup validation for production settings.

A misconfigured production deployment should fail while the process is booting,
where an operator is watching the logs, rather than while serving traffic.
Every check here raises :class:`~django.core.exceptions.ImproperlyConfigured`
with a message that names the offending variable and the fix.

The validators are plain functions with no Django settings import, so they can
be unit tested directly and reused by any settings module that wants to opt
into the same guarantees.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.core.exceptions import ImproperlyConfigured

#: Secret keys that ship with this repository or the Hatch environments. A
#: deployment that still uses one of these has an empty environment file, and
#: anyone can forge a JWT signed with a public key.
FORBIDDEN_SECRET_KEY_PREFIXES = (
    "unsafe-development-only",
    "unsafe-test-only",
    "django-insecure-",
)

#: Django's own minimum, and a practical floor for a token_urlsafe key.
MINIMUM_SECRET_KEY_LENGTH = 50

#: Hosts that turn every protection off or invite header spoofing.
FORBIDDEN_HOSTS = frozenset({"*", "testserver", ".local"})


def validate_secret_key(secret_key: str, *, environment: str) -> None:
    """Reject development secrets, short secrets, and secrets that look empty.

    Args:
        secret_key: The resolved ``DJANGO_SECRET_KEY``.
        environment: The resolved ``DJANGO_ENVIRONMENT``.

    Raises:
        ImproperlyConfigured: If the key is unusable in production.
    """
    if environment != "production":
        return

    if not secret_key or not secret_key.strip():
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY is empty. Generate one with "
            "'scripts/generate_secret_key.sh' and store it in your secret manager."
        )

    for prefix in FORBIDDEN_SECRET_KEY_PREFIXES:
        if secret_key.startswith(prefix):
            raise ImproperlyConfigured(
                "DJANGO_SECRET_KEY is still the checked-in development default "
                f"('{prefix}...'). Generate a unique key with "
                "'scripts/generate_secret_key.sh' before using production settings."
            )

    if len(secret_key) < MINIMUM_SECRET_KEY_LENGTH:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be at least "
            f"{MINIMUM_SECRET_KEY_LENGTH} characters in production; "
            f"the configured value is {len(secret_key)}. "
            "'scripts/generate_secret_key.sh' produces a suitable key."
        )

    if len(set(secret_key)) < 10:
        # Catches repeated-character filler that satisfies the length check.
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY has too little character variety. "
            "Generate a random key instead of padding a short one."
        )


def validate_allowed_hosts(allowed_hosts: Sequence[str], *, environment: str) -> None:
    """Require an explicit, wildcard-free host allowlist in production.

    Args:
        allowed_hosts: The resolved ``ALLOWED_HOSTS``.
        environment: The resolved ``DJANGO_ENVIRONMENT``.

    Raises:
        ImproperlyConfigured: If the allowlist is empty or contains a wildcard.
    """
    if environment != "production":
        return

    hosts = [host.strip() for host in allowed_hosts if host.strip()]
    if not hosts:
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS is required in production. List every hostname "
            "the API answers on, for example 'api.example.com'."
        )

    forbidden = sorted(set(hosts) & FORBIDDEN_HOSTS)
    if forbidden:
        raise ImproperlyConfigured(
            f"DJANGO_ALLOWED_HOSTS must not contain {forbidden} in production. "
            "A wildcard lets any host forge absolute URLs and poison caches, and "
            "'testserver' only exists for the test client."
        )


def validate_debug(debug: bool, *, environment: str) -> None:
    """Forbid ``DEBUG`` outside development and test.

    ``DEBUG`` leaks SQL, settings values, and tracebacks to whoever asks, so it
    is never negotiable through an environment variable in production: this
    check runs after the value is resolved and refuses to continue.
    """
    if environment == "production" and debug:
        raise ImproperlyConfigured(
            "DJANGO_DEBUG must be false in production. The production settings "
            "module never enables it, and this check exists so a hand-edited "
            "environment cannot either."
        )


def validate_query_logging(enabled: bool, *, environment: str) -> None:
    """Refuse SQL query logging in production."""
    if environment == "production" and enabled:
        raise ImproperlyConfigured(
            "DJANGO_LOG_QUERIES must be disabled in production. It forces the "
            "debug cursor on every query, which slows the database and writes "
            "parameter values into the log stream."
        )


def validate_production_settings(
    *,
    environment: str,
    secret_key: str,
    allowed_hosts: Sequence[str],
    debug: bool,
    query_logging: bool = False,
) -> None:
    """Run every production guard.

    Individual checks are exported so a caller can validate one concern in
    isolation; this function is the single entry point used by the settings
    module so there is exactly one ordering to reason about.
    """
    validate_debug(debug, environment=environment)
    validate_secret_key(secret_key, environment=environment)
    validate_allowed_hosts(allowed_hosts, environment=environment)
    validate_query_logging(query_logging, environment=environment)
