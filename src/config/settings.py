"""Django settings for the Budget Tracker project.

The domain and application layers remain independent of this module. Only
Django-facing infrastructure and interface adapters load these settings.
"""

from datetime import timedelta
from pathlib import Path
from typing import Any

import environ
from django.core.exceptions import ImproperlyConfigured

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
DEBUG = env.bool("DJANGO_DEBUG", default=ENVIRONMENT != "production")
_default_allowed_hosts = (
    [] if ENVIRONMENT == "production" else ["localhost", "127.0.0.1"]
)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=_default_allowed_hosts)
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])

if ENVIRONMENT == "production":
    if DEBUG:
        raise ImproperlyConfigured("DJANGO_DEBUG must be false in production.")
    if DJANGO_SECRET_KEY.startswith("unsafe-development-only"):
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be replaced before using production settings."
        )
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS is required in production.")
    if LOG_QUERIES:
        raise ImproperlyConfigured("DJANGO_LOG_QUERIES must be disabled in production.")

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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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

database_config["CONN_MAX_AGE"] = env.int("DJANGO_DATABASE_CONN_MAX_AGE", default=60)
database_config["CONN_HEALTH_CHECKS"] = True

if ENVIRONMENT == "production" and database_config["ENGINE"] != (
    "django.db.backends.postgresql"
):
    raise ImproperlyConfigured("Production must use the PostgreSQL database backend.")

DATABASES = {"default": database_config}

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

STATIC_URL = "static/"
STATIC_ROOT = PROJECT_ROOT / "staticfiles"

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

_secure_by_default = ENVIRONMENT == "production"
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=_secure_by_default)
SESSION_COOKIE_SECURE = env.bool(
    "DJANGO_SESSION_COOKIE_SECURE", default=_secure_by_default
)
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=_secure_by_default)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False
)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_AGE = env.int("DJANGO_SESSION_COOKIE_AGE", default=60 * 60 * 24 * 14)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

if ENVIRONMENT == "production":
    if not SECURE_SSL_REDIRECT:
        raise ImproperlyConfigured(
            "DJANGO_SECURE_SSL_REDIRECT must be true in production."
        )
    if not SESSION_COOKIE_SECURE or not CSRF_COOKIE_SECURE:
        raise ImproperlyConfigured(
            "Session and CSRF cookies must be secure in production."
        )
    if len(DJANGO_SECRET_KEY) < 32:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must contain at least 32 characters in production."
        )
    if "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured("Wildcard hosts are not allowed in production.")
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured("Production CSRF trusted origins must use HTTPS.")

if env.bool("DJANGO_TRUST_PROXY_HEADERS", default=False):

    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

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
    }
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
