"""Django settings for the Budget Tracker project.

The domain and application layers remain independent of this module. Only
Django-facing infrastructure and interface adapters load these settings.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import environ
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from config.schedules import DEFAULT_DAILY_PLAN_CRON, parse_daily_plan_cron
from config.validators import validate_production_settings

BASE_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BASE_DIR.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CSRF_TRUSTED_ORIGINS=(list, []),
    DJANGO_DATABASE_CONN_MAX_AGE=(int, 60),
    DJANGO_LOG_LEVEL=(str, "INFO"),
    DJANGO_LOG_QUERIES=(bool, False),
    DJANGO_SECURE_SSL_REDIRECT=(bool, False),
    DJANGO_SESSION_COOKIE_SECURE=(bool, False),
    DJANGO_CSRF_COOKIE_SECURE=(bool, False),
    DJANGO_TRUST_PROXY_HEADERS=(bool, False),
    DJANGO_SECURE_HSTS_SECONDS=(int, 0),
    DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=(bool, False),
    DJANGO_SECURE_HSTS_PRELOAD=(bool, False),
    DJANGO_SESSION_COOKIE_AGE=(int, 60 * 60 * 24 * 14),
    DJANGO_SESSION_COOKIE_SAMESITE=(str, "Lax"),
    DJANGO_CSRF_COOKIE_SAMESITE=(str, "Lax"),
    DJANGO_REFERRER_POLICY=(str, "same-origin"),
    DJANGO_PERMISSIONS_POLICY=(str, ""),
    DJANGO_NUM_PROXIES=(int, 0),
    DJANGO_CONNECT_TIMEOUT=(int, 0),
    DJANGO_STATEMENT_TIMEOUT_MS=(int, 30_000),
    DJANGO_MAX_OPERATIONS=(int, 60),
    CORS_ALLOWED_ORIGINS=(list, []),
    EMAIL_PORT=(int, 587),
)

if (PROJECT_ROOT / ".env").is_file():
    environ.Env.read_env(PROJECT_ROOT / ".env")

ENVIRONMENT = env("DJANGO_ENVIRONMENT", default="local").lower()
LOG_QUERIES = env.bool("DJANGO_LOG_QUERIES", default=False)
if ENVIRONMENT not in {"local", "production", "test"}:
    raise ImproperlyConfigured(
        "DJANGO_ENVIRONMENT must be one of: local, production, or test."
    )

DJANGO_SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="unsafe-development-only-settings-secret",
)
SECRET_KEY = DJANGO_SECRET_KEY

# DEBUG is never negotiable in production: it leaks SQL, settings, and
# tracebacks. The environment variable is still read so that a misconfigured
# deployment hears about it, but it cannot turn debugging on.
_requested_debug = env.bool("DJANGO_DEBUG", default=ENVIRONMENT != "production")
DEBUG = False if ENVIRONMENT == "production" else _requested_debug
if ENVIRONMENT == "production" and _requested_debug:
    raise ImproperlyConfigured(
        "DJANGO_DEBUG=true is not accepted when DJANGO_ENVIRONMENT=production. "
        "Remove the variable instead of relying on it being ignored."
    )
_default_allowed_hosts = (
    [] if ENVIRONMENT == "production" else ["localhost", "127.0.0.1"]
)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=_default_allowed_hosts)
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

# Fail at import time, before the process opens a socket, if the production
# environment is incomplete. Each guard raises with the variable name and the
# fix rather than booting into a half-secured state.
validate_production_settings(
    environment=ENVIRONMENT,
    secret_key=DJANGO_SECRET_KEY,
    allowed_hosts=ALLOWED_HOSTS,
    debug=DEBUG,
    query_logging=LOG_QUERIES,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "apps.users.apps.UsersConfig",
    "apps.transactions.apps.TransactionsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.profile.apps.ProfileConfig",
    "apps.rentals.apps.RentalsConfig",
    "apps.tasks.apps.TasksConfig",
    "apps.purchases.apps.PurchasesConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files straight from the container, so no separate
    # web server or CDN is required for a single-host deployment. It must stay
    # above everything that could generate a response using static URLs.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # Must sit above anything that can produce a response, so even a redirect
    # or a 404 raised below carries the CORS headers a browser-based front end
    # needs in order to read the error.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # Every DRF view is csrf_exempt, so this middleware governs only the
    # session-authenticated Django admin, which is the surface it protects.
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Fills in the policy headers Django's security settings do not cover.
    # Runs inside SecurityMiddleware, so it only adds headers that are absent.
    "shared.infrastructure.middleware.SecurityHeadersMiddleware",
]

if LOG_QUERIES:
    MIDDLEWARE.insert(1, "config.query_logging.QueryLoggingMiddleware")

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

_default_database_url = (
    "postgresql://budget_tracker:budget_tracker@localhost:5432/budget_tracker"
)
_database_url = env("DATABASE_URL", default=_default_database_url)
database_config: dict[str, Any] = env.db_url("DATABASE_URL", default=_database_url)
if ENVIRONMENT == "test":
    _test_database_url = env("TEST_DATABASE_URL", default=_database_url)
    test_database_config: dict[str, Any] = env.db_url(
        "TEST_DATABASE_URL", default=_test_database_url
    )
    test_database_config["TEST"] = {"NAME": test_database_config["NAME"]}
    database_config = test_database_config

# Connection handling. CONN_MAX_AGE keeps connections open between requests
# instead of reconnecting per request; CONN_HEALTH_CHECKS (Django 5.1+) makes
# the first query on a reused connection verify it is still alive, which turns
# a silently dead socket into a reconnect rather than an error.
#
# The statement timeout applies everywhere: PostgreSQL cancels a runaway query
# itself instead of leaving it to pin a Gunicorn worker until the request
# timeout kills the process.
#
# The connect timeout is a production-only default. psycopg treats it as the
# total budget for establishing a connection, retries included, and Docker's
# NAT plus embedded DNS regularly costs more than five seconds when a busy host
# is churning connections (a 300-test integration run reproduced it), which
# turns a healthy database into "connection timeout expired". Production has
# stable traffic patterns, so the budget is enforced there; set
# DJANGO_CONNECT_TIMEOUT explicitly to enforce it elsewhere, or to 0 to
# disable it entirely.
_connect_timeout = env.int("DJANGO_CONNECT_TIMEOUT", default=0)
_statement_timeout_ms = env.int("DJANGO_STATEMENT_TIMEOUT_MS", default=30_000)
database_config["CONN_MAX_AGE"] = env.int("DJANGO_DATABASE_CONN_MAX_AGE", default=60)
database_config["CONN_HEALTH_CHECKS"] = True

_database_options: dict[str, Any] = {}
if _statement_timeout_ms > 0:
    _database_options["options"] = f"-c statement_timeout={_statement_timeout_ms}"
if _connect_timeout > 0:
    _database_options["connect_timeout"] = _connect_timeout
elif ENVIRONMENT == "production":
    _database_options["connect_timeout"] = 5
database_config["OPTIONS"] = {**database_config.get("OPTIONS", {}), **_database_options}

if ENVIRONMENT == "production" and database_config["ENGINE"] != (
    "django.db.backends.postgresql"
):
    raise ImproperlyConfigured("Production must use the PostgreSQL database backend.")

DATABASES = {"default": database_config}

# Throttle counters and any other short-lived state live in the cache. With
# more than one web replica, a local-memory cache means each replica enforces
# its own share of the rate limits, so Redis is used whenever it is reachable.
# Redis is already a hard dependency for Celery, so this costs nothing.
_REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
if ENVIRONMENT != "test" and _REDIS_URL.startswith(("redis://", "rediss://")):
    # A dedicated logical database, so clearing the cache cannot discard
    # Celery's queued tasks and result keys.
    _redis_parts = urlsplit(_REDIS_URL)
    _cache_location = urlunsplit(
        (_redis_parts.scheme, _redis_parts.netloc, "/1", "", "")
    )
    CACHES: dict[str, dict[str, Any]] = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": _cache_location,
            "KEY_PREFIX": env.str("DJANGO_CACHE_KEY_PREFIX", default="life-utility"),
            # A throttle counter that outlives its window would keep rejecting
            # requests after the rate resets.
            "TIMEOUT": env.int("DJANGO_CACHE_TIMEOUT", default=3600),
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "life-utility-default",
        }
    }

# Cross-origin access for the browser-based front end (house-utility-control-
# front), which authenticates with a JWT bearer token in the Authorization
# header. Credentials are therefore unnecessary: no cookies cross origins, and
# refusing them keeps the API from becoming a CSRF target through the browser's
# ambient authority. CORS_ALLOWED_ORIGINS is an explicit allowlist; an empty
# list means no cross-origin request is answered at all.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=False)
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_METHODS = ["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"]
CORS_ALLOWED_HEADERS = [
    "Accept",
    "Accept-Language",
    "Authorization",
    "Content-Language",
    "Content-Type",
    "X-Requested-With",
]
# Preflight results are safe to cache for an hour; the origin allowlist decides
# correctness, this only saves a round trip.
CORS_PREFLIGHT_MAX_AGE = env.int("CORS_PREFLIGHT_MAX_AGE", default=3600)
CORS_URLS_REGEX = r"^/api/.*$"

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation."
        "UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env("DJANGO_LANGUAGE_CODE", default="en-us")
TIME_ZONE = env("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True


def _path_setting(name: str, default: Path) -> Path:
    """Read a filesystem path from the environment.

    An empty or whitespace-only value counts as unset. .env files routinely
    carry commented-out or blank entries, and Path("") silently resolves to the
    current directory, which would make Django collect static files into the
    repository instead of the intended location.
    """
    value = env.str(name, default="").strip()
    return Path(value) if value else default


STATIC_URL = "static/"
STATIC_ROOT = _path_setting("DJANGO_STATIC_ROOT", default=PROJECT_ROOT / "staticfiles")

# Uploaded files (avatars, rental documents) are served by the web container
# from MEDIA_ROOT, which the Compose production stack mounts from a named
# volume so they survive container replacement. A single-node disk is fine for
# this project; see the Deployment section of the README for moving to S3 or
# MinIO when the file volume outgrows one host.
MEDIA_URL = env.str("DJANGO_MEDIA_URL", default="media/")
MEDIA_ROOT = _path_setting("DJANGO_MEDIA_ROOT", default=PROJECT_ROOT / "media")

# Static files are served by WhiteNoise: compressed on the fly (gzip, and
# brotli when the client advertises it). The manifest storage hashes every
# filename on collectstatic, so the production cache header is immutable and
# safe to hand to a CDN. Development serves unhashed names, so it must not
# cache them at all or an edit would not show up until the browser gave up.
WHITENOISE_MAX_AGE = env.int(
    "DJANGO_STATIC_MAX_AGE",
    default=(60 * 60 * 24 * 365) if ENVIRONMENT == "production" else 0,
)

STORAGES: dict[str, dict[str, Any]] = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if ENVIRONMENT == "production"
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        )
    },
}
# An unhashed storage makes collectstatic fail loudly in production instead of
# silently emitting assets whose names change whenever their content does.
WHITENOISE_KEEP_ONLY_HASHED_FILES = ENVIRONMENT == "production"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
APPEND_SLASH = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "apps.users.interfaces.permissions.IsNotBanned",
    ],
    # Platform-wide limits. Views that need a stricter budget (login,
    # registration) add their own scoped throttle, and DRF applies every
    # applicable throttle, so the tightest limit wins.
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # A shared-NAT client (a household, an office, a mobile carrier) is
        # still a single identity here, so these are deliberately generous:
        # they exist to stop scraping, not to police normal use.
        "anon": env.str("THROTTLE_ANON_RATE", default="100/hour"),
        "user": env.str("THROTTLE_USER_RATE", default="1000/hour"),
        # Credential stuffing and mass sign-up get their own, much tighter
        # limits, applied by the views that own those endpoints.
        "login": env.str("THROTTLE_LOGIN_RATE", default="10/minute"),
        "register": env.str("THROTTLE_REGISTER_RATE", default="5/hour"),
    },
    # Number of trusted reverse proxies between the client and the app, used by
    # the throttles to recover the client address from X-Forwarded-For. Zero
    # means the immediate peer is the client. Behind a single TLS-terminating
    # proxy (Caddy in the reference deployment) this must be 1, or every client
    # shares the proxy's address and one caller can throttle everyone.
    # DRF reads this from REST_FRAMEWORK, not from a top-level Django setting.
    "NUM_PROXIES": env.int("DJANGO_NUM_PROXIES", default=0),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.api.exception_handler",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Budget Tracker API",
    "DESCRIPTION": (
        "JWT-authenticated personal budgeting API with owner-scoped "
        "transactions and pre-computed dashboard summaries."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "COMPONENT_SPLIT_REQUEST": True,
    "SECURITY": [{"Bearer": []}],
    "SECURITY_DEFINITIONS": {
        "Bearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    },
    "SORT_OPERATIONS": True,
    # Explicit names for choice sets that would otherwise be auto-numbered.
    # Two bounded contexts both call a field "priority" and both call another
    # "status"; without overrides the generator invents names like
    # "Priority3cdEnum", which change whenever an unrelated field is added.
    # The task and purchase-item priority enums share one name on purpose: they
    # are the same three values, so they can share one component.
    "ENUM_NAME_OVERRIDES": {
        # An override is matched on the (value, label) pairs of the choice
        # set, so the labels have to match the domain constants exactly.
        # Two bounded contexts both have a "priority" and a "status" field;
        # without overrides the generator invents names like
        # "Priority3cdEnum", which change whenever an unrelated field is
        # added. The task priority and the shopping-list priority declare the
        # same three values, so they legitimately share one component.
        "PriorityEnum": [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        "WishlistPriorityEnum": [
            ("must_have", "Must Have"),
            ("wanted", "Wanted"),
            ("nice_to_have", "Nice To Have"),
        ],
        "PurchaseItemStatusEnum": [("pending", "Pending"), ("purchased", "Purchased")],
        "PaymentStatusEnum": [
            ("PENDING", "Pending"),
            ("PARTIAL", "Partial"),
            ("PAID", "Paid"),
            ("OVERDUE", "Overdue"),
        ],
    },
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
    },
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14",
    "SWAGGER_UI_FAVICON_HREF": (
        "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/favicon-32x32.png"
    ),
}

if ENVIRONMENT == "production":
    SPECTACULAR_SETTINGS["SERVE_PUBLIC"] = False
    SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = [
        "rest_framework.permissions.IsAdminUser"
    ]
else:
    SPECTACULAR_SETTINGS["SERVE_PUBLIC"] = True
    SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] = ["rest_framework.permissions.AllowAny"]

if ENVIRONMENT == "test":
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Security ---------------------------------------------------------------
# Every value is environment-driven with a production-shaped default. Nothing
# here is hardcoded to a literal that an operator cannot override, except DEBUG
# above, which is treated as a fault rather than a preference.
#
# Note on SECURE_BROWSER_XSS_FILTER: Django removed that setting in 5.0, and
# the browser XSS auditor it enabled was itself deprecated. The equivalent
# protection here is SECURE_CONTENT_TYPE_NOSNIFF plus the CSP-style headers the
# security middleware adds, so there is deliberately no dead setting here.
_secure_by_default = ENVIRONMENT == "production"

# Transport. TLS is terminated by the reverse proxy (Caddy in the reference
# deployment), so the app must trust the forwarded scheme header instead of
# redirecting HTTP itself: a redirect loop is the classic symptom of getting
# this pair wrong.
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=_secure_by_default)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if env.bool("DJANGO_TRUST_PROXY_HEADERS", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS. One year, with subdomains and preload, is the specification's maximum
# effective duration. Preload is irreversible in practice (submission to the
# browser preload list cannot be withdrawn by the site owner), so it is
# enabled by default only because production is expected to be HTTPS-only;
# verify every subdomain serves HTTPS before leaving it on.
SECURE_HSTS_SECONDS = env.int(
    "DJANGO_SECURE_HSTS_SECONDS", default=31536000 if _secure_by_default else 0
)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=_secure_by_default
)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=_secure_by_default)

# Response hardening. SECURE_CONTENT_TYPE_NOSNIFF stops a browser from
# re-interpreting an API response as executable content; X_FRAME_OPTIONS and
# the middleware headers keep the admin out of a clickjacking frame.
SECURE_CONTENT_TYPE_NOSNIFF = True
# strict-origin-when-cross-origin keeps the full referrer for same-origin
# navigation and drops the path cross-origin, where a referrer URL can carry an
# identifier. Django emits this header itself; the value below is kept
# identical to the middleware default so the two never disagree.
SECURE_REFERRER_POLICY = env.str(
    "DJANGO_REFERRER_POLICY",
    default="strict-origin-when-cross-origin" if _secure_by_default else "same-origin",
)
X_FRAME_OPTIONS = env.str("DJANGO_X_FRAME_OPTIONS", default="DENY")

# Policy headers applied by shared.infrastructure.middleware. Django's
# SecurityMiddleware already sets nosniff, X-Frame-Options, and the referrer
# policy from the settings above, so those three arrive here as no-ops that only
# fill a gap if a setting is ever cleared. Permissions-Policy is the header
# Django has no setting for; an empty environment value removes it.
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": X_FRAME_OPTIONS,
    "Referrer-Policy": SECURE_REFERRER_POLICY,
    "Permissions-Policy": env.str(
        "DJANGO_PERMISSIONS_POLICY",
        default=(
            "accelerometer=(), autoplay=(), camera=(), display-capture=(), "
            "encrypted-media=(), fullscreen=(self), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), midi=(), payment=(), usb=()"
        ),
    ),
}

# Cookies. These only govern the Django admin; the API itself is stateless and
# authenticates with a bearer token. SameSite=Lax blocks the cookie on
# cross-site POSTs (CSRF) while still surviving a top-level navigation to the
# admin, which is the behaviour an operator expects when following a link.
SESSION_COOKIE_SECURE = env.bool(
    "DJANGO_SESSION_COOKIE_SECURE", default=_secure_by_default
)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=_secure_by_default)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = env.str("DJANGO_SESSION_COOKIE_SAMESITE", default="Lax")
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = env.str("DJANGO_CSRF_COOKIE_SAMESITE", default="Lax")
SESSION_COOKIE_AGE = env.int("DJANGO_SESSION_COOKIE_AGE", default=60 * 60 * 24 * 14)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Number of trusted reverse proxies is configured above, inside
# REST_FRAMEWORK, because that is where DRF reads it from when resolving the
# client address for throttling.

if ENVIRONMENT == "production":
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured(
            "DJANGO_SECURE_SSL_REDIRECT must be true in production."
        )
    if not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE:
        raise ImproperlyConfigured(
            "Session and CSRF cookies must be secure in production."
        )
    if any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS):
        raise ImproperlyConfigured("CORS_ALLOWED_ORIGINS must use HTTPS in production.")
    if CORS_ALLOW_CREDENTIALS:
        raise ImproperlyConfigured(
            "CORS_ALLOW_CREDENTIALS must stay false: this API authenticates with "
            "a bearer token, and allowing credentials would let a browser attach "
            "ambient authority to cross-origin calls."
        )
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured("Production CSRF trusted origins must use HTTPS.")

# --- Email ------------------------------------------------------------------
# No mail is sent by the API today (there is no password-reset flow); these
# settings exist so adding one does not mean re-deriving the configuration.
# The console backend is the default outside production precisely because
# printing credentials to logs is not an acceptable production default.
EMAIL_BACKEND = env.str(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.smtp.EmailBackend"
        if _secure_by_default
        else "django.core.mail.backends.console.EmailBackend"
    ),
)
EMAIL_HOST = env.str("EMAIL_HOST", default="localhost")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env.str("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env.str("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=False)
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL", default="noreply@localhost")
# Fail loudly rather than silently dropping a message that would have been a
# password reset.
SERVER_EMAIL = DEFAULT_FROM_EMAIL

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 60 * 10
CELERY_TASK_SOFT_TIME_LIMIT = 60 * 9
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_RESULT_EXPIRES = 60 * 60 * 24
CELERY_TASK_ALWAYS_EAGER = env.bool(
    "CELERY_TASK_ALWAYS_EAGER", default=ENVIRONMENT == "test"
)
CELERY_TASK_EAGER_PROPAGATES = ENVIRONMENT == "test"
CELERY_BEAT_SCHEDULE = {
    "reconcile-dashboard-summaries": {
        "task": "apps.dashboard.infrastructure.tasks.reconcile_user_dashboards",
        "schedule": 60 * 60 * 24,
        "options": {"expires": 60 * 30},
    },
    "generate-daily-plans": {
        "task": "apps.tasks.infrastructure.tasks.schedule_daily_plan_generation",
        "schedule": parse_daily_plan_cron(
            env("DAILY_PLAN_GENERATION_CRON", default=DEFAULT_DAILY_PLAN_CRON)
        ),
        # A morning run that is still queued an hour later is stale, and the
        # next day's run would duplicate it.
        "options": {"expires": 60 * 60},
    },
    "archive-completed-lists-daily": {
        "task": "apps.purchases.infrastructure.tasks.archive_completed_lists_celery",
        # 03:00 local time: late enough that a list completed late yesterday
        # is already counted, and quiet enough not to compete with the morning
        # plan generation an hour later.
        "schedule": crontab(hour=3, minute=0),
        "options": {"expires": 60 * 60 * 6},
    },
}

# Assistant (LLM) assistance for the tasks context. Defaults target a local
# Ollama daemon, which is the only provider this project supports: the whole
# point of the feature is that task data never leaves the machine.
OLLAMA_BASE_URL = env("OLLAMA_BASE_URL", default="http://localhost:11434")
OLLAMA_MODEL = env("OLLAMA_MODEL", default="llama3:8b")

LOGGING: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": env("CELERY_LOG_LEVEL", default="INFO"),
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("DJANGO_LOG_LEVEL", default="INFO"),
    },
}

if LOG_QUERIES:
    LOGGING["loggers"]["django.db.backends"] = {
        "handlers": ["console"],
        "level": "DEBUG",
        "propagate": False,
    }
