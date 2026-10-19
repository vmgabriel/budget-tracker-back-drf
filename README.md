# Life & Home Utility

Life & Home Utility is a containerized, secure, and modular personal life and
home management API built with Python 3.12+, Django 5.2, Django REST
Framework, PostgreSQL, Redis, and Celery. Its mission is to give one owner a
single, secure, centralized place to administer their life: their money, their
home, and the day-to-day obligations that come with both. The current release
is implemented end to end — identity, preferences and localization, financial
tracking with pre-computed summaries, and property/rental management.

The code follows Domain-Driven Design and Clean Architecture. Business rules
are pure Python; Django, DRF, Celery, and the database are adapters around
those rules. The same four-layer structure is the entry point for every future
area of life administration (tasks, habits, inventory, maintenance schedules),
each introduced as a new bounded context inside this monolith.

## Contents

- [Capabilities](#capabilities)
- [Architecture](#architecture)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API conventions](#api-conventions)
- [Authentication](#authentication)
- [Transactions](#transactions)
- [Dashboard](#dashboard)
- [Profile & Settings](#profile--settings)
- [Rentals & Property Management](#rentals--property-management)
- [Tasks, Goals & Daily Plans](#tasks-goals--daily-plans)
- [Shopping Lists & Wishlist](#shopping-lists--wishlist)
- [Celery and aggregation workflow](#celery-and-aggregation-workflow)
- [OpenAPI and Swagger](#openapi-and-swagger)
- [Sample data](#sample-data)
- [Testing and code quality](#testing-and-code-quality)
- [Performance](#performance)
- [Security review](#security-review)
- [Deployment](#deployment)
- [Development workflow](#development-workflow)
- [Troubleshooting](#troubleshooting)

## Capabilities

### Financial tracking

- UUID-based users with `free`, `pro`, and `premium` plans.
- JWT bearer authentication with one-hour access tokens and rotating seven-day
  refresh tokens.
- Password hashing and Django's standard password validators.
- Owner-only transaction CRUD with pagination and date validation.
- Transaction types: `income`, `expense`, `investment`, and `savings`.
- Owner-scoped funding accounts (`credit_card`, `debit`, `cash`, `savings`) that
  transactions can be linked to, so spending can be grouped per funding source.
- Dashboard totals for income and expenses; investment and savings records are
  retained but are not counted as income or expense.
- Daily, ISO-week (Monday–Sunday), and calendar-month summaries.
- Idempotent Celery tasks with retries for transient database failures.
- Owner-scoped dashboard reads that never aggregate financial data on the HTTP
  request path.
- Auto-provisioned per-user profiles with timezone, language, currency, and
  date-format preferences, which localize every other module.

### Property & rental management

- Houses and the apartments nested under them, each fully owner-scoped.
- Apartment documents (ID cards, lease contracts, employment certificates, and
  arbitrary attachments) with typed classification.
- Utility meter readings for water, electricity, and gas, with
  domain-computed consumption, unit cost, and monthly bills.
- Rent payments with an automatically derived `PAID`/`PARTIAL` status and a
  monthly summary reporting paid totals and outstanding balance.

### Task & goal management

- Tasks with `low`/`medium`/`high` importance, an hour estimate, a markdown
  description, an optional due date, and `todo`/`doing`/`done` status.
- Goals (macrotasks) grouping tasks under a shared outcome; deleting a goal
  keeps its tasks and only detaches them.
- One daily plan per user and day, holding the scheduled tasks and their summed
  hours, with a configurable stopping rule that refuses work once the daily
  budget is reached (defaults: 8 hours).
- An "overwhelmed" flag per task when its estimate passes the user's threshold
  (default: 4 hours), so a single oversized task is visible as such.
- Priority promotion for carried-over tasks, saturating at `high`.
- Fully owner-scoped: a task, goal, or plan belonging to somebody else answers
  `404`, never `403`.

### Shopping lists & wishlist

- Multiple named shopping lists per user, each with `high`/`medium`/`low`
  priority, items carrying a quantity, free-text details, and `pending` or
  `purchased` status.
- One wishlist per user (enforced by a database constraint), whose items also
  record a product link, an image link, a description, an estimated price, and
  a `must_have`/`wanted`/`nice_to_have` priority.
- A list completes when every one of its items is purchased; the completion
  date is stamped automatically, and buying the last outstanding item is what
  completes the list. Deleting an item that had completed a list reopens it.
- A list is completed only when it actually holds items: an empty list never
  completes, so a freshly created one is never mistaken for a finished one.
- Soft delete: removing a list hides it from the default views and keeps its
  items. Archived lists are listed separately and can be restored.
- Tags drawn from a shared catalogue, attached to items by name and idempotent:
  tagging the same concept twice never creates a second catalogue entry.
- Fully owner-scoped: a list, item, or wishlist belonging to somebody else
  answers `404`, never `403`.

### Foundation for life administration

- A modular monolith that accepts new bounded contexts — tasks, habits,
  inventory, maintenance schedules, and similar — without a migration of the
  existing ones.
- A single identity, profile, and authorization model shared by every context.
- OpenAPI 3 schema and Swagger UI generated from the interface layer.
- Health/readiness probes, structured error metadata, and optional local SQL
  query logging.
- Database-free unit tests and isolated PostgreSQL/Celery integration tests.

## Architecture

The application is a **Majestic Monolith**: one deployable unit, one
deployment pipeline, and one database, decomposed into bounded contexts that
own their own domain model. A single runtime keeps operations simple, while
the boundaries between contexts keep the domain coherent as it grows.

This structure is the foundation for a scalable life management system rather
than an implementation detail of the current modules. Every bounded context
under `src/apps/<module>/` has four layers:

```text
src/apps/<module>/
├── domain/                 # Pure Python; no Django, DRF, Celery, or DB
│   ├── entities.py         # Aggregates and entities
│   ├── value_objects.py    # Frozen, slotted value objects
│   ├── exceptions.py       # Domain-specific failures
│   └── rules.py            # Optional business rules
├── application/            # Use cases and dependency-inversion ports
│   ├── use_cases/          # One use case per file
│   ├── ports/              # typing.Protocol interfaces
│   └── __init__.py         # Public application exports
├── infrastructure/         # Django ORM, adapters, and Celery tasks
│   ├── persistence/
│   │   ├── models.py
│   │   └── repositories.py
│   ├── adapters/
│   └── tasks.py
└── interfaces/             # DRF serializers, views, and URLs
    ├── views.py
    ├── serializers.py
    └── urls.py
```

The dependency rule is:

```text
interfaces → application → domain
infrastructure → application ports
```

Domain and application code never import Django, DRF, Celery, PostgreSQL, or
an infrastructure module. Ports use `typing.Protocol`, dependencies are
injected into use cases, and time is accessed through the shared `Clock` port.
Stable generic ports live in `src/shared/` rather than being duplicated by a
bounded context.

The executable architecture tests in
`src/tests/unit/test_architecture.py` guard the framework-free domain and the
inward-only application dependency rule.

## Quick start

### Prerequisites

Required:

- Docker Engine with Docker Compose v2
- `make`

Optional for host-side quality checks:

- Python 3.12+
- Hatch

Verify the Compose installation:

```bash
docker compose version
```

### Start the stack

```bash
cd home-manage-utility-drf
make install                 # create .env only if it does not exist
make up                      # build and start web, worker, beat, PostgreSQL, Redis
make migrate                 # apply migrations
make superuser               # optional; create a staff administrator
```

The default endpoints are:

- API base URL: <http://127.0.0.1:8000> (use the versioned routes below)
- Swagger UI: <http://127.0.0.1:8000/api/docs/> (legacy alias: <http://127.0.0.1:8000/api/schema/swagger-ui/>)
- OpenAPI schema: <http://127.0.0.1:8000/api/schema/>
- Liveness: <http://127.0.0.1:8000/healthz>
- Readiness: <http://127.0.0.1:8000/readyz>
- Django admin: <http://127.0.0.1:8000/admin/>

Inspect or stop services:

```bash
make logs
make stop
make down
```

`make down` preserves PostgreSQL and Redis volumes. To deliberately erase local
data, use `docker compose down --volumes`; this is destructive.

To recreate containers while preserving volumes and applying migrations:

```bash
make repair
```

## Configuration

Copy `.env.example` to `.env` with `make install`. `django-environ` loads that
file for host-side Hatch commands; Compose overrides database and Redis URLs
with container-safe service names.

Important settings:

| Variable | Purpose |
| --- | --- |
| `DJANGO_ENVIRONMENT` | `local`, `test`, or `production` |
| `DJANGO_SECRET_KEY` | Django signing key; use a long random value in production |
| `DJANGO_DEBUG` | Must be `false` in production |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated host allowlist |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional origins retained for Django admin/browser surfaces |
| `DJANGO_TIME_ZONE` | Application time zone; defaults to `UTC` |
| `DATABASE_URL` | PostgreSQL URL for host-side commands |
| `DOCKER_DATABASE_URL` | PostgreSQL URL used inside Compose |
| `TEST_DATABASE_URL` | Isolated host-side test database URL |
| `DOCKER_TEST_DATABASE_URL` | Isolated tester database URL inside Compose |
| `REDIS_URL` / `DOCKER_REDIS_URL` | Celery broker and Redis URL |
| `CELERY_RESULT_BACKEND` | Celery result backend URL for host-side commands |
| `DOCKER_CELERY_RESULT_BACKEND` | Celery result backend URL inside Compose |
| `CELERY_TASK_ALWAYS_EAGER` | Run tasks synchronously; intended for tests only |
| `DJANGO_LOG_QUERIES` | Optional local SQL debug cursor and query logger |
| `DJANGO_LOG_LEVEL` | Root level; `DEBUG` in development and `INFO` in production and tests |
| `DJANGO_LOG_FORMAT` | `json` for one JSON object per line (production), `text` for a readable terminal |
| `DJANGO_LOG_REQUESTS` | Emit one access line per request carrying the same `X-Request-ID` |
| `DJANGO_LOG_SERVICE` | `service` field on every JSON line, to tell web, worker, and Beat apart |
| `DJANGO_LOG_FILE` | Optional rotating local log file in addition to stdout; empty in containers |
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS in production |
| `DJANGO_SESSION_COOKIE_SECURE` | Mark Django admin session cookies secure |
| `DJANGO_CSRF_COOKIE_SECURE` | Mark Django admin CSRF cookies secure |
| `DJANGO_TRUST_PROXY_HEADERS` | Trust `X-Forwarded-Proto` behind a controlled proxy |
| `DJANGO_SECURE_HSTS_SECONDS` | Optional HTTP Strict Transport Security duration |
| `DJANGO_STATIC_ROOT` / `DJANGO_MEDIA_ROOT` | Where WhiteNoise reads static files from and where uploads are written; the production Compose stack points both at named volumes |
| `DJANGO_STATIC_MAX_AGE` | Cache lifetime in seconds for hashed static files |
| `GUNICORN_WORKERS` | Optional worker count override; leave unset to derive `(2 * visible CPUs) + 1` |
| `WEB_PORT` / `WEB_BIND_ADDRESS` | Host port and bind address published for the web service |
| `BACKUP_DIR` / `RETENTION_DAYS` | Destination directory and retention window (days) for `scripts/backup_db.sh` |
| `BACKUP_INTERVAL_SECONDS` | Cadence of the Compose `backup` sidecar that runs `scripts/backup_loop.sh` (default 86400) |

The production resource ceilings (`WEB_MEMORY_LIMIT`, `WORKER_MEMORY_LIMIT`,
`DATA_MEMORY_LIMIT`, `CELERY_CONCURRENCY`, `DB_MAX_CONNECTIONS`,
`REDIS_MAXMEMORY`, and their CPU counterparts) are documented in the
[Deployment](#deployment) section.

For local SQL inspection, set `DJANGO_DEBUG=true`, `DJANGO_LOG_QUERIES=true`,
and use `DJANGO_LOG_LEVEL=DEBUG`. Query logging adds overhead and is rejected
when `DJANGO_ENVIRONMENT=production`.

## API conventions

### Base URL and versioning

All versioned application routes are aggregated once by
`src/apps/api/urls.py` and mounted under `/api/v1/`. JSON is the supported
request and response format (non-JSON request media types receive `415`).
Decimal monetary values are represented as JSON strings, for example
`"42.50"`. User authentication and management use the canonical
`/api/v1/users/...` resource paths. Django's browser-only `/api-auth/` helpers
are not part of the API.

### API authentication

Protected endpoints use JWT bearer authentication. Send the access token in
the `Authorization` header; do not put tokens in URLs or query parameters:

```text
Authorization: Bearer <access-token>
```

Access tokens expire after one hour. Refresh tokens expire after seven days
and are rotated when used; the default deployment does not blacklist rotated
tokens. API writes do not require a CSRF cookie or `X-CSRFToken` header.
Django sessions remain enabled only for the Django admin and other explicitly
session-based Django surfaces; API clients must not depend on those cookies.
Existing API clients should migrate by exchanging their email/password for a
token pair and then sending the access token on every subsequent request.

### Errors

All DRF errors include a stable envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid data.",
    "details": {
      "email": ["Enter a valid email address."]
    }
  },
  "detail": "The request contains invalid data.",
  "email": ["Enter a valid email address."]
}
```

`error.code` is one of the documented categories such as `validation_error`,
`not_authenticated`, `permission_denied`, `not_found`, `method_not_allowed`,
`throttled`, or `internal_server_error`. The top-level `detail` and field keys
are retained for backwards compatibility while clients migrate to `error`.
Unexpected exceptions are logged and return a generic 500 response without
internal details.

Common status codes are `201` for creation, `204` for deletion, `400` for
invalid input, `401` for missing, expired, or invalid bearer credentials,
`403` for insufficient permission, `404` for an unknown or non-owned resource,
and `500` for an unexpected server failure. Invalid login credentials also
return `401` with an `authentication_failed` error code. Clients should use the
`error.code` value rather than infer semantics from a legacy field.

### Pagination

User and transaction list endpoints accept `page` (1–10,000) and `page_size`
(1–100). The response envelope is:

```json
{
  "count": 42,
  "page": 1,
  "page_size": 20,
  "results": []
}
```

## Authentication

The user API exposes the following resource-oriented endpoints:

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/users/auth/register/` | Public | Create an account |
| `POST` | `/api/v1/users/auth/login/` | Public | Obtain an access/refresh pair |
| `POST` | `/api/v1/users/auth/refresh/` | Public | Rotate tokens and obtain access |
| `POST` | `/api/v1/users/auth/logout/` | Authenticated | Acknowledge client logout |
| `GET` | `/api/v1/users/me/` | Authenticated | Read the current user |
| `GET` | `/api/v1/users/` | Staff | List users |
| `GET` | `/api/v1/users/{id}/` | Staff | Read a user |
| `PATCH` | `/api/v1/users/{id}/` | Staff | Update email, name, or active state |
| `PATCH` | `/api/v1/users/{id}/plan/` | Staff | Change a user's plan |

### Register

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"alex@example.com","full_name":"Alex Morgan","password":"StrongPassword123!"}'
```

Response (`201 Created`):

```json
{
  "id": "8e9c5c2e-0e5a-4ca2-b8c6-7d6e3c1c1f01",
  "email": "alex@example.com",
  "full_name": "Alex Morgan",
  "plan": "free",
  "is_active": true,
  "is_staff": false,
  "is_superuser": false,
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-15T12:00:00Z"
}
```

### Obtaining a token

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"StrongPassword123!"}'
```

Response (`200 OK`):

```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user_id": "8e9c5c2e-0e5a-4ca2-b8c6-7d6e3c1c1f01",
  "email": "user@example.com",
  "full_name": "Alex Morgan"
}
```

### Using and refreshing tokens

Send the access token in the `Authorization` header:

```bash
curl -X GET http://127.0.0.1:8000/api/v1/transactions/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

Refresh an expiring access token with the refresh token:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh":"eyJ0eXAiOiJKV1QiLCJhbGc..."}'
```

The refresh response contains a new access token and, because refresh-token
rotation is enabled, a new refresh token. This deployment does not install
SimpleJWT's blacklist app, so logout is a client-side token discard and cannot
invalidate already-issued tokens before they expire:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/users/auth/logout/ \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### Using Swagger UI

1. Navigate to <http://127.0.0.1:8000/api/docs/>.
2. Obtain a token from `/api/v1/users/auth/login/`.
3. Click **Authorize** and enter the access token (the `Bearer` prefix is
   supplied by the Swagger UI).
4. Test protected endpoints; the token is persisted by the UI configuration.

### Staff user management

List users with `GET /api/v1/users/?page=1&page_size=20`. Update a profile
with a partial payload:

```json
{
  "full_name": "Alex M. Morgan",
  "is_active": true
}
```

Change a plan with:

```json
{"plan": "premium"}
```

Only staff users may access these endpoints. A non-owner transaction is
reported as `404`, rather than revealing that another user's resource exists.

## Transactions

Transaction endpoints require authentication and are always scoped to the
current user. Amounts must be positive, have at most two decimal places, and
be no larger than `9999999999.99`. Dates cannot be in the future.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/transactions/` | List the current user's transactions |
| `POST` | `/api/v1/transactions/` | Create a transaction |
| `GET` | `/api/v1/transactions/{id}/` | Retrieve an owned transaction |
| `PATCH` | `/api/v1/transactions/{id}/` | Partially update an owned transaction |
| `DELETE` | `/api/v1/transactions/{id}/` | Delete an owned transaction |
| `GET` | `/api/v1/transactions/accounts/` | List the current user's active funding accounts |
| `POST` | `/api/v1/transactions/accounts/` | Create a funding account |
| `GET` | `/api/v1/transactions/accounts/{id}/` | Retrieve an owned funding account |

### Create

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access-token>' \
  -d '{"amount":"42.50","transaction_type":"expense","category":"Food","date":"2026-01-15","description":"Lunch"}'
```

Response (`201 Created`):

```json
{
  "id": "c3b03b68-5e8b-4cf1-9fb7-9ef9c1ce6c4a",
  "amount": "42.50",
  "transaction_type": "expense",
  "category": "Food",
  "date": "2026-01-15",
  "description": "Lunch",
  "account_id": null,
  "account_name": null,
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-15T12:00:00Z"
}
```

`transaction_type` accepts `income`, `expense`, `investment`, or `savings`.
`description` is optional and is returned as `null` when blank. A partial
update may contain any subset of `amount`, `transaction_type`, `category`,
`date`, `description`, and `account_id`; an empty patch is rejected.

### Funding accounts

Create an account before linking transactions to it:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/accounts/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access-token>' \
  -d '{"name":"Main Card","account_type":"credit_card"}'
```

```json
{
  "id": "2f0f6f2c-6a41-4f4c-9a30-3b9a85d4a111",
  "name": "Main Card",
  "account_type": "credit_card",
  "is_active": true,
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-15T12:00:00Z"
}
```

`account_type` accepts `credit_card`, `debit`, `cash`, or `savings`. New
accounts are always active, and `GET /api/v1/transactions/accounts/` returns the
active ones only.

Send `account_id` when creating or patching a transaction to link it:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transactions/ \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <access-token>' \
  -d '{"amount":"42.50","transaction_type":"expense","category":"Food","date":"2026-01-15","account_id":"2f0f6f2c-6a41-4f4c-9a30-3b9a85d4a111"}'
```

Transactions expose the funding source as two flat read-only fields,
`account_id` and `account_name`, which keeps per-account charting simple for
clients. Both are `null` for unlinked transactions. An `account_id` that
belongs to another user (or does not exist) is reported as `404`, and sending
`null` in a patch is rejected: this phase links and re-links accounts, it does
not detach them. Deleting an account keeps its transactions and clears the
link (`SET_NULL`).

## Dashboard

Dashboard reads return persisted summaries only. The interface does not run a
financial aggregation query while serving a request, which keeps read latency
and query volume predictable. A missing summary is represented by an empty
collection or `null` overview slot until the asynchronous worker catches up.

| Method | Endpoint | Period | Purpose |
| --- | --- | --- | --- |
| `GET` | `/api/v1/dashboard/` | `period` query parameter, default `weekly` | Generic summary list |
| `GET` | `/api/v1/dashboard/daily/` | Daily | Daily summary list |
| `GET` | `/api/v1/dashboard/weekly/` | Weekly | Weekly summary list |
| `GET` | `/api/v1/dashboard/monthly/` | Monthly | Monthly summary list |
| `GET` | `/api/v1/dashboard/overview/` | Current snapshots | Today, this week, and this month |

The fixed-period endpoints reject a conflicting `period` query parameter. All
list endpoints accept optional inclusive `start_date` and `end_date` values;
the application bounds a requested range to 366 days. Without dates, the
current calendar period is used.

Example:

```bash
curl 'http://127.0.0.1:8000/api/v1/dashboard/monthly/?start_date=2026-01-01&end_date=2026-03-31' \
  -H 'Authorization: Bearer <access-token>'
```

List response:

```json
{
  "period": "monthly",
  "start_date": "2026-01-01",
  "end_date": "2026-03-31",
  "summary_count": 3,
  "is_empty": false,
  "has_stale_data": false,
  "summaries": [
    {
      "id": "e3a7db2a-f85a-41a1-8c93-fb5d4e7cf1a5",
      "period": "monthly",
      "date": "2026-01-01",
      "total_income": "3200.00",
      "total_expense": "1570.00",
      "net_balance": "1630.00",
      "generated_at": "2026-01-15T12:00:01Z",
      "is_stale": false,
      "stale_at": null,
      "status": "fresh"
    }
  ]
}
```

Overview response:

```json
{
  "as_of_date": "2026-01-15",
  "today": { "period": "daily", "date": "2026-01-15", "...": "..." },
  "this_week": { "period": "weekly", "date": "2026-01-12", "...": "..." },
  "this_month": { "period": "monthly", "date": "2026-01-01", "...": "..." }
}
```

Any overview slot may be `null` while its first snapshot is being generated.
`status` is derived from the persisted `is_stale` flag.

### Aggregation rules

- Business dates are anchored to each user's `Profile.timezone` local calendar
  (UTC system time is converted via `utc_to_local_date`); `SystemClock` keeps
  returning UTC. Set `DJANGO_TIME_ZONE` only for presentation/localization.
- Daily totals sum only `income` and `expense` transaction amounts.
- Weekly periods are ISO weeks beginning Monday and ending Sunday.
- Monthly periods are calendar months; weeks crossing a month boundary are
  clipped with daily rows so adjacent-month transactions are not counted twice.
- A rollup is marked stale when a required lower-level daily/weekly row is
  absent or stale.
- Historical fresh snapshots are immutable. A transaction change first marks
  affected snapshots stale, after which a worker can safely replace them.
- `investment` and `savings` are valid transaction types but intentionally do
  not contribute to `total_income` or `total_expense` in this MVP.

## Profile & Settings

Every account owns exactly one profile with personal details and regional
preferences. Profiles are provisioned automatically when a user registers: a
`post_save` signal copies the account name and applies the configured
defaults (`UTC`, `es`, `USD`, `YYYY-MM-DD`), so these endpoints always return
data for authenticated users. All of them require JWT bearer authentication
(`Authorization: Bearer <access-token>`).

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/profile/me/` | Read the current user's profile |
| `PATCH` | `/api/v1/profile/me/` | Update name, timezone, avatar, or bio |
| `PATCH` | `/api/v1/profile/me/preferences/` | Update language, currency, or date format |

Both patch endpoints accept partial payloads; omitted fields stay unchanged
and empty payloads are rejected. `avatar_url` and `bio` are cleared by
sending an empty string. Field rules: `timezone` must be a valid IANA name
such as `America/Bogota`, `language` an ISO 639-1 code such as `en` or `pt`,
`currency` an ISO 4217 code such as `USD` or `COP`, and `date_format` one of
`YYYY-MM-DD`, `DD/MM/YYYY`, or `MM/DD/YYYY`. `bio` is limited to 500
characters.

Update details:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/profile/me/ \
  -H 'Authorization: Bearer <access-token>' \
  -H 'Content-Type: application/json' \
  -d '{"first_name": "Ana", "timezone": "America/Bogota", "bio": "Life admin in one place."}'
```

Response:

```json
{
  "id": "b3f0c2d4-1a2b-4c5d-8e9f-0a1b2c3d4e5f",
  "first_name": "Ana",
  "last_name": "Garcia",
  "timezone": "America/Bogota",
  "language": "es",
  "currency": "USD",
  "date_format": "YYYY-MM-DD",
  "avatar_url": null,
  "bio": "Life admin in one place.",
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-16T09:30:00Z"
}
```

Update preferences:

```bash
curl -X PATCH http://127.0.0.1:8000/api/v1/profile/me/preferences/ \
  -H 'Authorization: Bearer <access-token>' \
  -H 'Content-Type: application/json' \
  -d '{"language": "pt", "currency": "COP", "date_format": "DD/MM/YYYY"}'
```

Users created before the profile module existed have no profile row. The
idempotent backfill command provisions them using the same defaults as the
registration signal and reports how many were created:

```bash
make backfill-profiles
```

## Rentals & Property Management

Rentals endpoints manage houses, apartments, apartment documents, monthly
utility readings, and rent payments. All of them require JWT bearer
authentication (`Authorization: Bearer <access-token>`) and are always scoped
to the current user: a user can only see houses they own and the resources
nested under them. Attempts to access another user's resources return `404
Not Found` (never `403`) so existence is never leaked.

### Houses

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rentals/houses/` | List the current user's houses |
| `POST` | `/api/v1/rentals/houses/` | Create a house |
| `GET` | `/api/v1/rentals/houses/{id}/` | Retrieve an owned house |
| `PATCH` | `/api/v1/rentals/houses/{id}/` | Partially update name or address |
| `DELETE` | `/api/v1/rentals/houses/{id}/` | Delete an owned house |

### Apartments

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rentals/apartments/?house_id={id}` | List apartments of a house |
| `POST` | `/api/v1/rentals/apartments/` | Create an apartment (`house_id` in body) |
| `GET` | `/api/v1/rentals/apartments/{id}/` | Retrieve an owned apartment |
| `PATCH` | `/api/v1/rentals/apartments/{id}/` | Partially update number/floor/rent |
| `DELETE` | `/api/v1/rentals/apartments/{id}/` | Delete an owned apartment |

### Documents

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rentals/apartments/{apartment_id}/documents/` | List apartment documents |
| `POST` | `/api/v1/rentals/apartments/{apartment_id}/documents/` | Upload a document |
| `GET` | `/api/v1/rentals/documents/{id}/` | Retrieve a document |
| `DELETE` | `/api/v1/rentals/documents/{id}/` | Delete a document |

`document_type` accepts `ID_CARD`, `LEASE_CONTRACT`,
`EMPLOYMENT_CERTIFICATE`, or `OTHER`.

### Utility readings

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rentals/apartments/{apartment_id}/utilities/` | List readings (`utility_type`, `start_date`, `end_date` filters) |
| `POST` | `/api/v1/rentals/apartments/{apartment_id}/utilities/` | Record a reading |
| `GET` | `/api/v1/rentals/utilities/{id}/` | Retrieve a reading |
| `GET` | `/api/v1/rentals/apartments/{apartment_id}/utilities/bill/?utility_type=WATER&year=2026&month=1` | Aggregated bill for a month |

`utility_type` accepts `WATER`, `ELECTRICITY`, or `GAS`. The response
includes the fields the domain calculates:

```json
{
  "id": "c3b03b68-5e8b-4cf1-9fb7-9ef9c1ce6c4a",
  "apartment_id": "9b5b2f54-ce0a-4c0a-9ef9-c1ce6c4a5e8b",
  "utility_type": "WATER",
  "reading_date": "2026-01-31",
  "current_reading": "120.50",
  "previous_reading": "100.00",
  "consumption": "20.50",
  "unit_cost": "0.5000",
  "total_cost": "10.25",
  "created_at": "2026-01-31T12:00:00Z"
}
```

`consumption = current_reading - previous_reading` (must be non-negative,
otherwise the request returns `400`) and `total_cost = consumption *
unit_cost` (rounded to cents). A duplicate `(apartment, utility_type,
reading_date)` is rejected with `400` (enforced by a `UniqueConstraint` and
checked at the application layer first).

### Payments

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/rentals/apartments/{apartment_id}/payments/` | List payments (`start_date`, `end_date` filters) |
| `POST` | `/api/v1/rentals/apartments/{apartment_id}/payments/` | Record a payment |
| `GET` | `/api/v1/rentals/payments/{id}/` | Retrieve a payment record |
| `PATCH` | `/api/v1/rentals/payments/{id}/` | Partially update amount/status/notes |
| `GET` | `/api/v1/rentals/apartments/{apartment_id}/payments/summary/?year=2026&month=1` | Aggregated monthly summary |

Recording a payment auto-calculates `status` from the amount versus the
apartment rent: `PAID` when the amount covers the full rent, `PARTIAL`
otherwise. Aggregation returns the current posture of the apartment for the
requested month:

```json
{
  "apartment_id": "9b5b2f54-ce0a-4c0a-9ef9-c1ce6c4a5e8b",
  "year": 2026,
  "month": 1,
  "total_paid": "300.00",
  "outstanding_balance": "200.00",
  "payment_count": 1
}
```

## Tasks, Goals & Daily Plans

The context is mounted under `/api/v1/tasks/`, and every route states its domain
explicitly inside `src/apps/tasks/interfaces/urls.py`. No router is involved,
so the repetition in `/api/v1/tasks/tasks/` is deliberate: the prefix identifies
the bounded context, the segment after it identifies the resource.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/tasks/tasks/` | List my tasks; filter with `?status=` and `?goal_id=` |
| `POST` | `/api/v1/tasks/tasks/` | Create a task |
| `GET` | `/api/v1/tasks/tasks/<id>/` | Read one task |
| `PATCH` | `/api/v1/tasks/tasks/<id>/` | Update the sent fields only |
| `DELETE` | `/api/v1/tasks/tasks/<id>/` | Delete one task |
| `POST` | `/api/v1/tasks/tasks/<id>/mark-doing/` | Start a task |
| `POST` | `/api/v1/tasks/tasks/<id>/mark-done/` | Complete a task, stamping `completed_at` |
| `POST` | `/api/v1/tasks/tasks/<id>/reopen/` | Send a completed task back to `todo`, clearing `completed_at` |
| `POST` | `/api/v1/tasks/tasks/<id>/promote-priority/` | Raise importance by one level |
| `POST` | `/api/v1/tasks/tasks/<id>/evaluate/` | Queue an assistant assessment (`202`) |
| `POST` | `/api/v1/tasks/tasks/<id>/decompose/` | Queue an assistant decomposition (`202`) |
| `GET` | `/api/v1/tasks/tasks/llm-health/` | Check that the assistant daemon answers |
| `GET`/`POST` | `/api/v1/tasks/goals/` | List or create goals |
| `GET`/`PATCH`/`DELETE` | `/api/v1/tasks/goals/<id>/` | Read, update, or delete a goal |
| `POST` | `/api/v1/tasks/goals/<id>/link-task/` | Attach `{"task_id": "<uuid>"}` |
| `POST` | `/api/v1/tasks/goals/<id>/unlink-task/` | Detach `{"task_id": "<uuid>"}` |
| `GET`/`POST` | `/api/v1/tasks/daily-plans/` | List days, or open one with `{"date": "YYYY-MM-DD"}` |
| `POST` | `/api/v1/tasks/daily-plans/generate/` | Queue an assistant plan for a day (`202`); body `{"date": "YYYY-MM-DD"}` is optional |
| `GET`/`PATCH`/`DELETE` | `/api/v1/tasks/daily-plans/<id>/` | Read, flag, or discard a day |
| `POST` | `/api/v1/tasks/daily-plans/<id>/add-task/` | Schedule `{"task_id": "<uuid>"}` |
| `POST` | `/api/v1/tasks/daily-plans/<id>/remove-task/` | Unschedule `{"task_id": "<uuid>"}` |

Create a task:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/tasks/tasks/ \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "Water the plants",
        "description": "Every three days",
        "importance": "medium",
        "estimated_hours": "1.50",
        "due_date": "2026-02-01"
      }'
```

```json
{
  "id": "0f0d9a3d-6d0c-4a25-9b0f-5a1b0d2c9f11",
  "goal_id": null,
  "name": "Water the plants",
  "description": "Every three days",
  "due_date": "2026-02-01",
  "importance": "medium",
  "estimated_hours": "1.50",
  "status": "todo",
  "is_overwhelmed": false,
  "is_checked_by_llm": false,
  "llm_evaluation_failed": false,
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-15T12:00:00Z",
  "completed_at": null
}
```

`completed_at` is read-only: the server stamps it when a task reaches `done`,
and `POST /tasks/<id>/reopen/` clears it again. A task that was never completed
reports `null`.

### Partial updates and deadlines

`PATCH` only touches the fields it receives: omitting `due_date` keeps the
stored deadline, while sending `"due_date": null` clears it. An empty `PATCH`
body is rejected with `400`.

### Planning budgets

Two product defaults live in `src/apps/tasks/application/config.py` and reach
the use cases through an injected `PlanningPolicy`:

- `OVERWHELMED_THRESHOLD_HOURS` (`4.0`) — an estimate above this marks a task
  as `is_overwhelmed`.
- `DAILY_PLAN_MAX_HOURS` (`8.0`) — once a day reaches this many hours,
  `add-task` answers `409` until something is removed.

They are values, not domain rules: Phase 2 will resolve them per user from the
profile, and the assistant assistance described below already reuses the same
policy through `PlanningPolicy`.

### Status codes beyond the usual envelope

| Situation | Status |
| --- | --- |
| Resource missing **or** owned by somebody else | `404` |
| Rejected input (validation, unknown enum, empty `PATCH`) | `400` |
| `DailyPlanFull`, `TaskAlreadyInPlan`, `TaskAlreadyDone` | `409` |

### Assistant assistance

Task assessment, decomposition, and day planning run against a local
[Ollama](https://ollama.com) daemon: `OLLAMA_BASE_URL` (default
`http://localhost:11434`) and `OLLAMA_MODEL` (default `llama3:8b`). Task content
never leaves the machine.

Three properties define the feature:

- **Asynchronous.** An HTTP request only enqueues work and answers `202`. No
  view and no use case ever calls the model; every LLM call happens in
  `src/apps/tasks/infrastructure/tasks.py`.
- **Optional.** The daemon may be absent, slow, or unhelpful. Every failure is
  recorded on the entity (`llm_evaluation_failed`) and reported as a warning,
  so the feature degrades instead of failing. Nothing returns a `500` because
  Ollama is down, and retries cover the database only - an unreachable model is
  not transient, so re-running a paid prompt would help nobody.
- **Explicit.** Nothing is evaluated automatically. Editing a task never
  re-triggers the assistant, which matters because an evaluation overwrites
  `importance` and `estimated_hours`. `POST .../evaluate/` always re-evaluates,
  because asking twice is a deliberate request.

```text
POST /api/v1/tasks/tasks/<id>/evaluate/    → evaluate_task_celery
POST /api/v1/tasks/tasks/<id>/decompose/   → decompose_overwhelming_task_celery
POST /api/v1/tasks/daily-plans/generate/   → generate_daily_plan_celery
GET  /api/v1/tasks/tasks/llm-health/       → 200 {"status": "ok", "model": ...}
                                             503 {"status": "unavailable"}
```

`POST /daily-plans/generate/` is the manual counterpart of the nightly job: it
plans a day on demand, with an optional `{"date": "YYYY-MM-DD"}` body (today when
omitted), and answers `202`. The result is read back from the day itself, since
the assistant's answer arrives after the response.

### Automatic daily plans

`celery_beat` queues `schedule_daily_plan_generation` each morning, which
enqueues one `generate_daily_plan_celery` job per active user. The time comes
from `DAILY_PLAN_GENERATION_CRON` (standard five-field cron, default
`0 6 * * *`); only the hour and minute may vary, and an unparseable value logs a
warning and falls back to 06:00 rather than preventing the worker from booting.

```text
celery beat (06:00)
  → schedule_daily_plan_generation
    → generate_daily_plan_celery(user_id, <that user's local date>)
```

Two details worth knowing:

- **The scheduler only enqueues.** Its database work is two indexed reads, so it
  does not slow down or lock anything as the backlog grows.
- **Each user gets their own calendar day.** A user in UTC-5 would otherwise
  receive tomorrow's plan at six in the morning.

Without a running `celery_beat`, the other two assistance endpoints still work;
only the automatic morning plan is missing.

`evaluate_task_celery` sets `importance` and `estimated_hours`, and marks the
task `is_checked_by_llm`. `decompose_overwhelming_task_celery` does nothing
below the overwhelmed threshold; above it, it creates a goal plus the proposed
subtasks (inheriting the deadline, starting at `low` importance) and marks the
original `done` rather than deleting it, so a poor suggestion stays
recoverable. `generate_daily_plan_celery` fills a day from the owner's `todo`
backlog and **recomputes the stored hours from the real estimates**, because a
model that miscounts should not be able to write a day whose hours disagree
with its own tasks. It drops invented task ids rather than trusting them.

Editing a task's name, description, or due date resets `is_checked_by_llm`, so a
stale assessment is never mistaken for a current one.

## Shopping Lists & Wishlist

All routes live under `/api/v1/purchases/` and are owner-scoped: a resource
belonging to another user answers `404`, never `403`, so a caller cannot probe
for the existence of somebody else's data.

### Shopping lists

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `shopping-lists/` | List the caller's active lists |
| `POST` | `shopping-lists/` | Create a list (`name`, optional `priority`) |
| `GET` | `shopping-lists/inactive/` | List the caller's soft-deleted lists |
| `GET` | `shopping-lists/<uuid>/` | Retrieve one list with its items |
| `PATCH` | `shopping-lists/<uuid>/` | Rename a list or change its priority |
| `DELETE` | `shopping-lists/<uuid>/` | Soft-delete: hides the list, keeps its items |
| `POST` | `shopping-lists/<uuid>/restore/` | Bring a soft-deleted list back |
| `POST` | `shopping-lists/<uuid>/add-item/` | Add an item (`name`, `quantity`, `details`) |
| `PATCH` | `shopping-lists/<uuid>/items/<uuid>/` | Update one item |
| `DELETE` | `shopping-lists/<uuid>/items/<uuid>/` | Delete one item |
| `POST` | `shopping-lists/<uuid>/items/<uuid>/mark-purchased/` | Flag an item as bought |
| `POST` | `shopping-lists/<uuid>/items/<uuid>/tags/` | Attach tags by name (`tag_names`) |
| `DELETE` | `shopping-lists/<uuid>/items/<uuid>/tags/` | Detach tags by id (`tag_ids`) |

A nested item URL is only honoured when the item really belongs to the
addressed list, so `shopping-lists/A/items/B/` answers `404` when `B` lives in
another one of the caller's lists.

`POST`ing to `shopping-lists/` with `{"name": "Weekly groceries", "priority":
"high"}` returns `201` and the list body. Deleting a list returns `200` with
`is_active: false` rather than `204`, because a soft delete has a state the
caller can act on — the list is retrievable and restorable afterwards.

### Completion and archival

`status` on a list means "every item has been purchased", and `completed_at`
records when that became true. It is derived, never set by hand:

- Buying the last outstanding item completes the list and stamps `completed_at`.
- Deleting an item from a completed list reopens it and clears the date, so a
  list never claims to be finished while it still has something to buy.
- A list with no items is never completed. Without this rule the vacuous truth
  of "all zero items are purchased" would give a brand-new list a completion
  date and archive it a week later.
- The domain exposes `should_archive(current_date, archive_delay)` as a pure
  predicate for a completed list older than the delay (default 7 days, from
  `PURCHASES_DEFAULTS["ARCHIVE_DELAY_DAYS"]`). A nightly Celery Beat entry,
  `archive-completed-lists-daily` at 03:00, runs the sweep.

### Wishlist

One wishlist per user, enforced by a one-to-one constraint on the user. The
first `GET` creates it; later reads return the same one.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `wishlist/` | Retrieve the caller's wishlist, creating it on first access |
| `PATCH` | `wishlist/` | Rename the wishlist |
| `POST` | `wishlist/add-item/` | Add a wanted product |
| `PATCH` | `wishlist/items/<uuid>/` | Update one item |
| `DELETE` | `wishlist/items/<uuid>/` | Delete one item |
| `POST` | `wishlist/items/<uuid>/mark-purchased/` | Flag an item as bought |
| `POST` | `wishlist/items/<uuid>/tags/` | Attach tags by name (`tag_names`) |
| `DELETE` | `wishlist/items/<uuid>/tags/` | Detach tags by id (`tag_ids`) |

An item accepts `name`, `link`, `image_link`, `description`, `estimated_price`
(non-negative), and `priority` (`must_have`, `wanted`, `nice_to_have`).

### Tags

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `tags/` | List the whole catalogue |
| `POST` | `tags/` | Add an entry (`name`), idempotent |

The catalogue is shared across users, and the slug is derived from the name.
Creating a tag that already exists returns the existing row with `201` rather
than failing, so a client can tag without first checking the catalogue.

## Celery and aggregation workflow

The dashboard app registers transaction lifecycle signals in
`DashboardConfig.ready()`. The normal flow is:

```text
transaction commit
  → post_save/post_delete signal
  → transaction.on_commit()
  → invalidate_user_dashboard_cache(user_id, affected_dates)
  → generate_daily_summary for each affected date
  → generate_weekly_summary for the affected week
  → generate_monthly_summary for the affected month
```

The invalidation task marks all affected daily, weekly, and monthly rows stale
before enqueueing daily work. Rollup tasks regenerate the lower-level rows they
need and then enqueue their parent. All writes are transactional, and
`transaction.on_commit` prevents work for a transaction that later rolls back.

The task functions are:

- `invalidate_user_dashboard_cache(user_id, affected_dates)`
- `generate_daily_summary(user_id, target_date)`
- `generate_weekly_summary(user_id, target_date)`
- `generate_monthly_summary(user_id, target_date)`
- `reconcile_user_dashboards()` (scheduled daily by Celery Beat)
- `archive_completed_lists_celery()` (scheduled daily by Celery Beat, 03:00)

They use ISO date strings and UUID strings at the broker boundary. Summary
identity is unique on `(user, period, date)`, and repository writes use an
upsert, making retries and duplicate deliveries safe. Database
`OperationalError` failures are retried with exponential backoff and jitter,
up to five retries. Permanent domain/command errors are not retried indefinitely.
Tasks use late acknowledgement and reject-on-worker-lost settings configured in
`config/settings.py`. Generation tasks lock the owning user row while reading
lower-level data and replacing snapshots, preventing an older concurrent
calculation from overwriting a newer one. Celery Beat runs
`reconcile_user_dashboards` once per day;
it refreshes the current month for every active user so a day with no new
transaction still receives zero-valued daily and rollup snapshots. The
Compose `celery_beat` service is part of the default stack; an external
scheduler can call the same task in a larger deployment.

`archive_completed_lists_celery` is the archival sweep for the purchases
context. Each night it selects the shopping lists and wishlists that are still
active but already completed, asks the domain whether each has outlived its
delay, and soft-deletes the ones that have. Two properties are worth knowing:

- **It re-reads a candidate's items before deciding.** Completion is a claim
  about every item, and the candidate query does not hydrate them. Skipping that
  step would make every list look like it had nothing bought on it, and the
  sweep would archive nothing at all.
- **It only ever reads active rows and writes a one-way flag**, so a retry after
  a partial run archives whatever the first attempt missed and re-touches
  nothing. The task logs the counts it examined and archived.

The delay comes from `ArchiveDelayReader`, a port that currently answers with
`PURCHASES_DEFAULTS["ARCHIVE_DELAY_DAYS"]` for every user. It is the seam where
a per-user preference would be introduced; until then the 7-day default applies
uniformly. A corrupt stored value falls back to the default rather than raising
out of a periodic job.

For local integration tests, `CELERY_TASK_ALWAYS_EAGER=true` executes tasks
synchronously and `CELERY_TASK_EAGER_PROPAGATES=true` exposes task failures.
Do not use eager mode in production: the web request would perform worker
work.

## OpenAPI and Swagger

`drf-spectacular` generates an OpenAPI 3 document from the DRF interfaces.
The document's API contract version is `1.0.0`; the package's MVP release
version is `0.1.0`.

- Schema YAML/JSON: <http://127.0.0.1:8000/api/schema/>
- Swagger UI: <http://127.0.0.1:8000/api/docs/> (legacy alias: <http://127.0.0.1:8000/api/schema/swagger-ui/>)

The schema covers the versioned DRF API routes; health probes, Django admin,
and the removed `/api-auth/` browser helpers are intentionally outside the
OpenAPI document. In local/test environments the schema is public for
discovery. Production schema and Swagger routes require a staff bearer token by
default. The schema declares an HTTP `Bearer` security scheme, and the login
and refresh operations are public.

Regenerate/check the document during development with:

```bash
hatch run default:python manage.py spectacular --file /tmp/budget-tracker-schema.yml --validate
```

## Sample data

For a local demo, create three users (Free, Pro, and Premium), several months
of transactions, and immediately available dashboard summaries:

```bash
make shell
# Inside the Django shell:
from django.core.management import call_command
call_command("create_sample_data", months=3)
```

Or from the host/container command line:

```bash
docker compose exec web python manage.py create_sample_data --months 3
```

The command is idempotent for its `[sample:...]` transaction markers and can be
run repeatedly. Its default password is `SamplePassword123!`; override it with
`--password` for a private environment:

```bash
docker compose exec web python manage.py create_sample_data \
  --months 3 --password 'Use-A-Local-Password-123!'
```

The command uses direct, deterministic generation rather than relying on a
running worker, so it is useful in demonstrations and integration tests. It
refuses to run when `DJANGO_ENVIRONMENT=production` and does not delete
unrelated application data.

For imports or bulk writes that bypass model signals, rebuild a bounded range
synchronously:

```bash
docker compose exec web python manage.py rebuild_dashboard --months 3
# Optional single-user backfill:
docker compose exec web python manage.py rebuild_dashboard \
  --months 3 --user-id '<uuid>'
```

The rebuild command is safe to repeat and regenerates the daily sources before
weekly and monthly rollups.

## Testing and code quality

### Test layers

Unit tests are database-free and run locally:

```bash
make test-unit
# Equivalent:
hatch run test:pytest src/tests/unit -m unit
```

Integration tests use the isolated `test_budget_tracker` PostgreSQL database
and the `tester` Compose service:

```bash
make test-integration
```

Run both layers with:

```bash
make test
```

Tests are explicitly marked `unit` or `integration`; pytest uses strict marker
validation. Integration tests cover Django repositories, DRF endpoints, owner
isolation, migrations/constraints, transaction signals, Celery task
registration, idempotency, retries, and sample-data generation.

### Linting and formatting

```bash
make lint       # Ruff, Black --check, and mypy
make format     # Ruff fixes and Black formatting
make check      # Django system checks
```

The quality target is clean Ruff, Black, mypy, and Django checks before a
release. Keep docstrings and type annotations current when adding public
classes or functions.

Useful Make targets include:

| Target | Purpose |
| --- | --- |
| `make check` | Run Django system checks |
| `make migrations-check` | Fail when model changes lack migrations |
| `make schema` | Validate and generate the OpenAPI document |
| `make collectstatic` | Collect static files in the web container |
| `make lint` / `make format` | Run or apply Python quality checks |
| `make token` / `make refresh-token` | Generate JWTs from the running container |
| `make test-unit` / `make test-integration` | Run the isolated test layers |
| `make test` | Run both test layers |
| `make prod-release` / `make prod-up` / `make prod-logs` | Build, migrate, collect static, and run the hardened production stack |
| `make check-deploy` | Run Django's deployment checks against the real production environment |
| `make backup-db` | Timestamped `pg_dump` into `BACKUP_DIR` with 7-day retention |
| `make restore-db` | Validate and restore a dump: `make restore-db FILE=backups/backup_*.dump [ARGS='--dry-run']` |

## Performance

The implementation keeps expensive work out of request handlers:

- Transaction lists use owner/date indexes and bounded pagination.
- Daily aggregation uses a composite owner/date/type index for filtered sums.
- Dashboard summaries have a unique natural key and an owner/period/date index
  supplied by that constraint, plus a stale-row lookup index.
- Dashboard reads select persisted rows and do not scan transactions.
- Celery work is split by date and period so a transaction change only refreshes
  affected rollups; each task uses database transactions and idempotent upserts.
- Connection reuse is controlled by `DJANGO_DATABASE_CONN_MAX_AGE`, health
  checks are enabled, and queries are bounded by a server-side
  `statement_timeout`.

For large datasets, monitor query plans with `EXPLAIN ANALYZE`, tune PostgreSQL
statistics/autovacuum, and consider a reporting read replica. Do not remove
the pre-computation boundary without measuring its effect on p95 latency.

## Security review

The current security posture includes:

- Django password validators and one-way password hashing.
- Short-lived JWT access tokens and rotating refresh tokens.
- Owner-scoped repositories that return not-found rather than cross-user data.
- Staff-only user-management permissions.
- Parameterized Django ORM queries; user input is never interpolated into SQL.
- Generic 500 responses with server-side exception logging.
- `ALLOWED_HOSTS`, HSTS, proxy-header, and content-type protections in production
  settings, with startup validation that refuses a weak secret, a wildcard
  host, or `DEBUG=true`.
- Response hardening headers (`nosniff`, frame denial, referrer and permissions
  policy) on every response, including error paths.
- Rate limiting on every request, with dedicated budgets for login and
  registration, keyed on the real client address when a proxy is in front.
- An explicit cross-origin allowlist for the browser front end, with credentialed
  cross-origin requests refused outright.

JWT API requests use the `Authorization` header and do not require CSRF
handling; `CsrfViewMiddleware` is installed and governs the session-based Django
admin, which is the surface it protects. Django session settings remain relevant
to that separately served admin surface; do not use those cookies as API
credentials.
Registration and login are intentionally public JSON endpoints; protect them
with gateway throttling, origin controls, and abuse monitoring before exposing
them publicly. Logout cannot revoke a stateless token before its expiry, so
clients must discard tokens and operators should use short access-token
lifetimes and protected transport.

Before an internet-facing deployment:

1. Set a unique, stable signing secret, `DJANGO_DEBUG=false`, HTTPS, and an
   explicit host/origin allowlist.
2. Put the web service behind a TLS-terminating reverse proxy and do not expose
   PostgreSQL or Redis publicly.
3. Keep the throttles enabled and set `DJANGO_NUM_PROXIES` to the real number of
   proxies in front of the app; see
   [Rate limiting](#deployment) for what a wrong value costs.
4. Keep `CORS_ALLOWED_ORIGINS` limited to the front end's exact origin. The
   policy is in place; adding a wildcard or a loose prefix is what turns it into
   a liability.
5. Rotate credentials, restrict admin access, and review dependency updates.
6. Keep detailed query logging disabled in production.
7. Run `make check-deploy` and keep its output empty.

Rate limiting and CORS are now implemented in the application (see
[Deployment](#deployment)); what remains deployment-specific is the *tuning*,
not the mechanism.

## Deployment

### Production stack

`docker-compose.prod.yml` is a production override applied on top of the
development Compose file. The development file keeps the source tree bind-mounted
and publishes PostgreSQL and Redis on loopback for convenience; neither belongs
on a production host, and the override removes both:

```bash
# Development (unchanged)
docker compose up -d

# Production: hardened stack
make prod-release          # build, migrate, collectstatic, start
make prod-logs
make prod-down
```

The override changes, in order of why they matter:

| Concern | Production behaviour |
| --- | --- |
| Exposed ports | Only the web port is published, bound to `127.0.0.1:8000` by default so a reverse proxy on the same host is the only caller. PostgreSQL (5432) and Redis (6379) have no published ports at all; they are reachable only from the Compose network. |
| Restart policy | `restart: always` on every service, so a crash or host reboot recovers without a human. |
| Resource limits | `deploy.resources.limits` (CPU and memory) on web, Celery worker/Beat, PostgreSQL, and Redis, with reservations for scheduling. A leaking worker now dies alone instead of dragging the host into an OOM. Tunable via `WEB_MEMORY_LIMIT`, `WORKER_MEMORY_LIMIT`, `DATA_MEMORY_LIMIT`, and their CPU counterparts. |
| Healthchecks | `web` polls `/readyz`, `db` uses `pg_isready`, and `redis` uses `redis-cli ping`. `depends_on: service_healthy` means nothing starts against an unready database. |
| Application server | Gunicorn with the checked-in `src/config/gunicorn.conf.py` instead of ad-hoc CLI flags. |
| Log rotation | `json-file` with `max-size`/`max-file`, because the default driver grows without bound until the disk is full. |
| Volumes | `media_data` (uploads) and `static_data` (collected static) are named volumes, so files survive container replacement. |
| PostgreSQL | `max_connections` is set explicitly, which is the number the Gunicorn worker/thread arithmetic has to stay under. |
| Redis | `appendonly yes`, a `maxmemory` ceiling, and `noeviction`, because dropping a queued Celery task is worse than refusing a write. |
| Test service | The `tester` service is re-profiled to `never`, so `--profile test` cannot start it in production by accident. |

The `!override`/`!reset` merge tags require Docker Compose v2.24 or newer.

### Release sequence

The image is multi-stage, installs runtime dependencies only, and runs as the
unprivileged UID/GID `10001`. Migrate and collect static files as release jobs,
before the new web replicas start, not from every container:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm web python manage.py migrate --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  run --rm web python manage.py collectstatic --noinput
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  up -d --remove-orphans
```

`make prod-release` is exactly those four steps. Because `collectstatic` writes
hashed filenames, an old replica that is still serving during the rollout keeps
serving valid, immutable files, and the new replicas pick up the new ones when
they start; no cache purge is required at either end.

### Gunicorn

`src/config/gunicorn.conf.py` is the single source of truth for the WSGI
server. Defaults, all overridable through the environment:

| Setting | Default | Reasoning |
| --- | --- | --- |
| `workers` | `(2 * visible CPUs) + 1`, or `GUNICORN_WORKERS` | Handlers are mostly waiting on PostgreSQL, so two workers per core keeps cores busy while one is blocked on I/O. The CPU count honours `sched_getaffinity`, so a container limited to part of the host does not size itself for the whole machine. |
| `threads` | 4 (`GUNICORN_THREADS`) | Cheap for IO-bound reads; each thread also costs one database connection. |
| `timeout` | 60s (`GUNICORN_TIMEOUT`) | Headroom for slow reports without letting a stuck request hold a connection. Long work belongs in Celery. |
| `graceful_timeout` | 30s (`GUNICORN_GRACEFUL_TIMEOUT`) | In-flight requests finish after a `SIGTERM`, matching a 45s Compose stop grace period. |
| `accesslog` / `errorlog` | `-` | Docker logging drivers only capture stdout/stderr; writing to files inside the container would lose them. |
| `loglevel` | `info` (`GUNICORN_LOG_LEVEL`) | Lower it to `warning` when the access log is too chatty. |
| `max_requests` | 1000 + 100 jitter | Bounds the damage from slow memory growth instead of waiting for a crash. |

Tuning rules of thumb:

- Keep `workers * threads` comfortably below PostgreSQL `max_connections`,
  leaving room for migrations, backups, and manual admin work.
- Leave a core for PostgreSQL, Redis, and the Celery worker if they share the
  host, and keep `WORKER_CPUS_LIMIT` consistent with `WEB_CPUS_LIMIT`.
- Change one number at a time and watch p95 latency and worker CPU saturation.
- Verify a change before shipping it: `gunicorn --check-config -c
  src/config/gunicorn.conf.py config.wsgi:application`.

### Static and media files

Static assets are served by [WhiteNoise](https://whitenoise.evans.io/) from
inside the web container, so a single host needs no second web server and no CDN
to serve `/static/`:

- In production, `STORAGES["staticfiles"]` is
  `whitenoise.storage.CompressedManifestStaticFilesStorage`. `collectstatic`
  hashes every filename and writes a manifest, which is what makes the
  far-future immutable cache header (`DJANGO_STATIC_MAX_AGE`, one year by
  default) safe. WhiteNoise also compresses on the fly (gzip, plus brotli when
  the client advertises it).
- In development the plain `StaticFilesStorage` is used, so edits appear
  without a rebuild, and the static cache lifetime drops to zero because
  unhashed filenames must not be cached.
- Collect static files as a release step (`make prod-release`), before the web
  container starts serving with `WHITENOISE_KEEP_ONLY_HASHED_FILES`, which
  fails loudly if an unhashed file slipped through.
- Put a CDN in front of `/static/` once traffic warrants it. Hashed filenames
  mean no cache purge is needed; just lower the cache header if you want to
  retire files sooner.

Uploaded files (avatars, rental documents) live in `MEDIA_ROOT`, mounted from
the `media_data` named volume in the production stack and from the repository
path in development. The volume survives `docker compose down` and container
replacement, but it is still a single disk on one host: **it is not a backup,
and it does not scale horizontally.**

For a larger deployment, move media to object storage with
`django-storages` (S3, MinIO, or any S3-compatible endpoint), point
`DEFAULT_FILE_STORAGE`/`STORAGES["default"]` at it, and serve files through
short-lived signed URLs instead of the Django view. Do that before scaling the
web tier past one host; a shared filesystem is not a substitute for object
storage, and it is the usual cause of "works locally, loses uploads" incidents.

### Database and queue operations

Backups are handled by `scripts/backup_db.sh`, which writes a timestamped
`pg_dump` in custom format and prunes old copies:

```bash
# On a host with a published database port (development layout)
make backup-db                                   # writes to ./backups
BACKUP_DIR=/srv/backups RETENTION_DAYS=14 make backup-db

# In the production stack, where port 5432 is not published: the script runs
# inside the database container, where pg_dump and the credentials already are.
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -u root db sh -c 'BACKUP_DIR=/backups RETENTION_DAYS=7 /scripts/backup_db.sh'
```

Run it from host cron. The override mounts `./scripts` read-only into the
database container precisely so this works without exposing the port:

```cron
# /etc/cron.d/budget-tracker-backup  (m/h dom mon dow  command)
17 3 * * * cd /srv/life-utility && docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T -u root db sh -c 'BACKUP_DIR=/backups RETENTION_DAYS=7 /scripts/backup_db.sh' >> /var/log/life-utility-backup.log 2>&1
```

Or run the dedicated backup sidecar that ships with the production stack. It
runs `scripts/backup_loop.sh`, which takes one dump immediately and then every
`BACKUP_INTERVAL_SECONDS` (default 86400 = daily), and writes to the
`backup_data` volume:

```bash
# Bring the production stack up with the backup sidecar enabled.
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --profile backup up -d

# The loop runs backup_db.sh unchanged, so the job is identical to the manual
# one; the sidecar only supplies the schedule. Its journal is at
# /backups/backup.log inside the backup_data volume.
```

A `SIGTERM` stops the loop after the run in flight finishes rather than killing
`pg_dump` mid-stream.

The script is defensive on purpose, because a backup job that fails quietly is
worse than no job:

- Custom format (`-Fc`), so restoration is `pg_restore --list` or a selective
  `pg_restore`, not a plain SQL replay.
- Written to a `.partial` file and moved into place only on success, so a crash
  mid-dump never leaves a truncated archive under a name that looks valid.
- Verified with `pg_restore --list` before it reports success.
- Retention (`find ... -mtime "+$RETENTION_DAYS"`, default 7 days) runs *after*
  the new dump succeeds, so a failed run can never delete the last good copy.
- Refuses to start with less than 100 MB free, and prints the exact restore
  command for the file it just wrote.

Restore with `scripts/restore_db.sh` (or `make restore-db`). It validates the
archive with `pg_restore --list` before touching anything, and a dry run opens
no database connection at all:

```bash
# Validate the archive and print the plan; changes nothing.
scripts/restore_db.sh --dry-run backups/backup_20240101_030000.dump
make restore-db FILE=backups/backup_20240101_030000.dump ARGS='--dry-run'

# Apply it, into a scratch database first.
PGDATABASE=budget_tracker_scratch scripts/restore_db.sh --yes backups/backup_*.dump
```

A real restore runs `pg_restore --clean --if-exists` inside a single
transaction, so it is atomic: a failure anywhere rolls back and leaves the
target unchanged. The target is never guessed — it comes from `--database`,
`PGDATABASE`, or `POSTGRES_DB` — and the operator must retype the database name
(or pass `--yes`) before anything is dropped, which is what keeps a restore
from landing on the live database by accident.

Run the restore with a `pg_restore` whose major version matches the server. A
client older than the `pg_dump` that wrote the file refuses it
(`unsupported version in file header`); a newer one can emit settings the
server does not know (for example `transaction_timeout` against PostgreSQL 16).
The `postgres:16-alpine` image the stack already runs carries a matching client,
so restore from inside the database container, where the production override
already mounts `./scripts`:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  cp backups/backup_20240101_030000.dump db:/tmp/restore.dump
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec -T -e PGDATABASE=budget_tracker_scratch db \
  /scripts/restore_db.sh --yes /tmp/restore.dump
```

Two things a dump cannot do on its own: **test a restore.** Periodically restore
into a scratch database (`pg_restore --clean --if-exists --no-owner --dbname
scratch backup_*.dump`) and confirm the row counts. And **copy dumps off the
host** — a backup on the same disk as the database is lost by the same failure
that took the database down. Encrypt and ship them to object storage.

Alongside backups:

- Monitor replication, disk, connection counts, and migration status.
- Run at least one Celery worker and one Beat scheduler (the Compose defaults
  provide both). Scale workers horizontally with `CELERY_CONCURRENCY`; the
  configured prefetch multiplier of one avoids holding many jobs in one worker.
- Monitor task failures, retries, queue latency, stale summary counts, and
  worker memory. Alert on repeated `OperationalError` or a growing Redis queue.
- Celery task results expire after one day by default; the database summaries,
  not the result backend, are the durable dashboard record.

### Production environment

Production is selected with `DJANGO_ENVIRONMENT=production`; there is no
separate settings module, and nothing about the default development
configuration changes. Set at minimum:

```text
DJANGO_ENVIRONMENT=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<at least 50 random characters; keep stable while tokens are valid>
DJANGO_ALLOWED_HOSTS=api.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://api.example.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_TRUST_PROXY_HEADERS=true
DJANGO_LOG_QUERIES=false
DJANGO_NUM_PROXIES=1
CORS_ALLOWED_ORIGINS=https://bff.yourdomain.com
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
```

Everything else has a production-shaped default. The full list, with comments,
is in `.env.example` under "Production security".

#### Generating the secret key

```bash
scripts/generate_secret_key.sh                    # prints an 86-character key
scripts/generate_secret_key.sh --env-file         # DJANGO_SECRET_KEY=<key>
DJANGO_SECRET_KEY=$(scripts/generate_secret_key.sh)
```

The script draws 64 bytes from the operating system CSPRNG (`secrets`), so two
runs never produce the same value. The key signs session cookies, CSRF tokens,
password-reset tokens, and — through SimpleJWT's `SIGNING_KEY` — the access and
refresh tokens themselves, so anyone holding it can mint a token for any user.
Keep it in a secret manager, out of source control, and identical across
replicas. Rotating it invalidates every issued token and session: rotate
deliberately, not during a release.

Production settings refuse to start on a development secret, a secret shorter
than 50 characters or with too little variety, an empty or wildcard
`ALLOWED_HOSTS`, `DJANGO_DEBUG=true`, query logging, an HTTP CSRF or CORS
origin, insecure cookies, or `CORS_ALLOW_CREDENTIALS=true`. The checks live in
`src/config/validators.py`, run at import time, and name the variable and the
fix — a half-secured process never opens a socket.

`DJANGO_SECURE_HSTS_PRELOAD` defaults to on in production. Preload is
effectively irreversible once a browser has it, so confirm every subdomain
serves HTTPS before leaving it enabled. Keep database and Redis URLs in a secret
manager, not in source control.

#### Validating the production configuration

```bash
make check-deploy   # manage.py check --deploy, with the real production env
```

or, against an environment you have exported:

```bash
DJANGO_ENVIRONMENT=production python manage.py check --deploy
```

The target should report no issues. It covers the security settings Django can
verify by itself: secret strength, cookie flags, HSTS, redirect and proxy
handling, host/origin allowlists, and the presence of the CSRF middleware.

#### CORS and the browser front end

`house-utility-control-front` is a browser client on a different origin, so the
API answers cross-origin requests for exactly one origin:

```text
CORS_ALLOWED_ORIGINS=https://bff.yourdomain.com
```

- Exact origins only: scheme, host, port. No wildcard, no trailing slash, and
  no prefix matching (`https://bff.example.com.evil.test` must not match).
- HTTPS only in production; an `http://` origin is refused at startup.
- `CORS_ALLOW_CREDENTIALS` stays `false` and cannot be switched on in
  production. The front end authenticates with `Authorization: Bearer <jwt>`, so
  no cookie needs to cross origins, and allowing credentials would let a browser
  attach ambient authority to a cross-origin call. If a future client needs
  cookie sessions, that is a design change, not a configuration change.
- CORS applies to `/api/...` only (`CORS_URLS_REGEX`), so the Django admin is
  unaffected.
- Preflight responses are cached for an hour; the origin allowlist is what
  decides correctness.
- `CSRF_TRUSTED_ORIGINS` is separate and only matters for the session-based
  Django admin, never for the JWT API.

Leave the list empty when the API has no browser client: every cross-origin
request is then refused, which is the correct default for a server-to-server
deployment.

#### Rate limiting

Throttling is on by default for every request, with tighter budgets on the two
endpoints that accept untrusted input:

| Scope | Default | Applies to |
| --- | --- | --- |
| `anon` | `100/hour` | Any unauthenticated request |
| `user` | `1000/hour` | Any authenticated request, per account |
| `login` | `10/minute` | `POST /api/v1/users/auth/token/` |
| `register` | `5/hour` | `POST /api/v1/users/auth/register/` |

Behavior worth knowing:

- The counters live in Django's cache, which is Redis (logical database 1)
  outside the test environment. With more than one web replica that matters:
  a process-local cache would let each replica allow its own share.
- Anonymous requests are keyed by client address, recovered from
  `X-Forwarded-For` when `DJANGO_NUM_PROXIES` matches the number of proxies in
  front of the app. **With that count wrong, every client shares one bucket and
  a single noisy caller locks everyone out.** Behind a single TLS-terminating
  proxy such as Caddy, it is `1`.
- Authenticated requests are keyed by account, so a shared household or office
  connection does not collide.
- A view that declares its own `throttle_classes` (login and registration do)
  replaces the platform-wide defaults for that view, and the scoped rate is the
  one that applies.
- Exceeding a limit returns `429` with `Retry-After`, in the standard error
  envelope as `"code": "throttled"`. Successful attempts count too: a valid
  login consumes the budget, which is what stops a password-spraying run from
  simply retrying until one guess lands.
- Raise the rates through the environment if a shared NAT legitimately exhausts
  them; the defaults are intentionally generous for that reason.

#### Response headers

Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options:
DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and a
`Permissions-Policy` that denies camera, microphone, geolocation, payment, USB,
and similar APIs the application never uses. They come from
`shared.infrastructure.middleware.SecurityHeadersMiddleware`, which only fills
in headers that are absent, so it composes with Django's own security
middleware and with headers added by the reverse proxy. A Content Security
Policy is deliberately absent: the same process serves the Django admin, whose
templates would need per-page exceptions.

#### Database connection handling

`CONN_MAX_AGE=60` reuses connections between requests,
`CONN_HEALTH_CHECKS=True` (Django 5.1+) verifies a reused connection before
trusting it, and a `statement_timeout` of 30 seconds makes PostgreSQL cancel a
runaway query instead of letting it pin a Gunicorn worker until the request
timeout kills the process. A 5-second connect timeout applies in production
only; set `DJANGO_CONNECT_TIMEOUT` to enforce it elsewhere, or `0` to disable.

Keep `workers * threads` below PostgreSQL `max_connections`: every worker and
thread holds a connection for up to `CONN_MAX_AGE` seconds.

Also configure `DJANGO_SECURE_HSTS_SECONDS` after confirming the entire domain is
HTTPS-only. The single-host stack above is a deliberate baseline; for a larger
deployment, use managed PostgreSQL/Redis, secret injection, an orchestrator, and
private service networking.

### Health and observability

- `/healthz` is a dependency-free liveness probe.
- `/readyz` checks PostgreSQL and should be used as the load-balancer readiness
  probe; it is also the Compose healthcheck for the web container.
- Timestamped application, Django, and Celery logs go to stdout/stderr and can
  be collected by the platform's log agent. Gunicorn writes both streams there
  too, and the Compose log driver is capped so they cannot fill the disk.
- In production the logs are one JSON object per line (`timestamp`, `level`,
  `logger`, `service`, `message`, plus the request context), so a shipper can
  index them without a grok pattern. Development keeps the readable text format;
  `DJANGO_LOG_FORMAT` overrides either.
- Every request gets an `X-Request-ID`: taken from the inbound header when a
  gateway or front end supplies one, generated otherwise, returned on the
  response (and exposed through CORS), and bound to every log record emitted
  while handling it. That id is what ties an access line to the view, the
  repository, and the error that followed it. The application error handler
  deliberately does not expose stack traces to clients.

### Continuous integration

`.github/workflows/ci.yml` runs on every push to `main` and every pull request
against it, in three jobs:

| Job | Runs | Notes |
| --- | --- | --- |
| `lint` | `make lint` | Ruff, `black --check`, and mypy. |
| `test` | `make test` | The database-free unit layer through Hatch (including the architecture test that keeps the domain layer framework-free), then the integration layer in the Compose `tester` service against real PostgreSQL and Redis; dumps service logs on failure. |
| `production` | `make schema`, `make check-deploy` | Validates the OpenAPI schema, both Compose files, the Gunicorn config, and the ops scripts, then runs Django's deploy checks against the real production stack with a production-shaped `.env`. |

Any failing job fails the build. No credentials are needed beyond the
throwaway values `make install` writes from the checked-in template, and the
`test` service is never started on pull requests from forks.

Locally, the same gates are `make lint`, `make test`, `make check-deploy`, and
`make schema`.

## Development workflow

### Add a bounded context

A new bounded context is the unit of growth for life administration: it must
serve a coherent part of the centralized life/home management vision and own
its rules end to end. Build it as follows.

1. Create `src/apps/<module>/{domain,application,infrastructure,interfaces}`.
2. Keep entities/value objects pure and use `@dataclass(frozen=True, slots=True)`
   for immutable value objects.
3. Declare ports with `typing.Protocol`; do not import Django in application or
   domain code.
4. Implement adapters/repositories under `infrastructure` and inject them from
   an interface composition module.
5. Add serializers, views, and URLs under `interfaces`; aggregate URLs only in
   `src/apps/api/urls.py`.
6. Add unit tests for domain/use cases and integration tests for adapters and
   HTTP behavior.
7. Run `make lint`, `make test-unit`, and relevant integration tests.

Version control is owned by the maintainer. Automated tooling and AI agents
working on this repository must not stage, commit, tag, branch, or rewrite
history; they produce changes, verify them, and report a summary for review.
See the "Git Workflow" section of `AGENTS.md`.

### Add a Celery task

1. Put task code in the owning context's `infrastructure/tasks.py`.
2. Inject/use application use cases rather than duplicating business rules.
3. Make the natural database key and writes idempotent.
4. Retry only transient failures such as `OperationalError`; bound retries and
   emit useful structured logs.
5. Schedule follow-up work only after the surrounding transaction commits.
6. Add task registration, success, duplicate/retry, and signal integration tests.

### Architecture decision records

Significant decisions should be recorded under `docs/adr/` using this format:

```text
# ADR-NNN: Short decision title
- Status: Accepted
- Date: YYYY-MM-DD
- Context: What problem and constraints existed?
- Decision: What was chosen and why?
- Consequences: What becomes easier, harder, or operationally expensive?
- Alternatives: What was considered and rejected?
```

The current baseline decisions are: JWT bearer authentication for API clients
(ADR-005), explicit four-layer Clean Architecture, pre-computed dashboard
snapshots, and natural-key idempotency for asynchronous work. ADR-002 records
the original session-based MVP decision and is superseded by ADR-005 for API
clients. ADR-006 records the expansion of the project scope from personal
finance to personal life and home management.

## Troubleshooting

### A container is unhealthy

```bash
docker compose ps
make logs
docker compose exec web python manage.py check
docker compose exec web python manage.py migrate --showmigrations
```

If a previous stack has stale network attachments, `make repair` recreates the
containers while preserving volumes.

In the production stack, `db` and `redis` are reachable only from inside the
Compose network. If a tool outside the stack cannot connect, check that it is
using the service name (`db`, `redis`) on the project network rather than
`localhost:5432`; there is deliberately no published port.

A web container that restarts in a loop immediately after `make prod-up` is
usually static files: production uses the hashed manifest storage, so
`collectstatic` must run before the container serves traffic. Use
`make prod-release`, or run the `collectstatic` release job by hand.

### Dashboard data is empty or stale

Dashboard rows are generated asynchronously after a committed transaction.
Check that `celery_worker` and `celery_beat` are running, inspect worker logs,
and confirm the transaction was not created with `bulk_create` outside the
signal-aware workflow. Bulk APIs bypass model signals; use the scheduled
reconciliation task for current periods and a controlled backfill procedure for
historical ranges. For a deterministic local dataset, run `create_sample_data`.

### JWT authentication failures

Confirm that the client sends `Authorization: Bearer <access-token>` (with one
space and the exact `Bearer` capitalization), that the access token has not
expired, and that the signing key is identical across web replicas. Use the
refresh endpoint to obtain a new access token; do not send the refresh token as
an access token. A `401` response includes the stable `not_authenticated` or
`authentication_failed` error code.

### Local tests cannot connect

`make test-unit` does not need a database. `make test-integration` starts the
Compose database and Redis services and uses `DOCKER_TEST_DATABASE_URL`; check
that no stale `.env` overrides the expected service URLs.
