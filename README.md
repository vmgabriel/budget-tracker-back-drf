# Budget Tracker

Budget Tracker is a containerized personal finance API built with Python 3.12+,
Django 5.2, Django REST Framework, PostgreSQL, Redis, and Celery. The MVP is
implemented end to end: JWT bearer authentication, owner-scoped transactions,
and pre-computed daily, weekly, and monthly dashboard summaries.

The code follows Domain-Driven Design and Clean Architecture. Business rules
are pure Python; Django, DRF, Celery, and the database are adapters around
those rules.

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

- UUID-based users with `free`, `pro`, and `premium` plans.
- JWT bearer authentication with one-hour access tokens and rotating seven-day
  refresh tokens.
- Password hashing and Django's standard password validators.
- Owner-only transaction CRUD with pagination and date validation.
- Transaction types: `income`, `expense`, `investment`, and `savings`.
- Dashboard totals for income and expenses; investment and savings records are
  retained but are not counted as income or expense.
- Daily, ISO-week (Monday–Sunday), and calendar-month summaries.
- Idempotent Celery tasks with retries for transient database failures.
- Owner-scoped dashboard reads that never aggregate financial data on the HTTP
  request path.
- Auto-provisioned per-user profiles with timezone, language, currency, and
  date-format preferences.
- Owner-scoped rentals: houses, apartments, documents, utility readings, and
  rent payments with domain-computed consumption, billing, and payment status.
- OpenAPI 3 schema and Swagger UI.
- Health/readiness probes, structured error metadata, and optional local SQL
  query logging.
- Database-free unit tests and isolated PostgreSQL/Celery integration tests.

## Architecture

Every bounded context under `src/apps/<module>/` has four layers:

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
cd budget-tracker
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
| `DJANGO_SECURE_SSL_REDIRECT` | Redirect HTTP to HTTPS in production |
| `DJANGO_SESSION_COOKIE_SECURE` | Mark Django admin session cookies secure |
| `DJANGO_CSRF_COOKIE_SECURE` | Mark Django admin CSRF cookies secure |
| `DJANGO_TRUST_PROXY_HEADERS` | Trust `X-Forwarded-Proto` behind a controlled proxy |
| `DJANGO_SECURE_HSTS_SECONDS` | Optional HTTP Strict Transport Security duration |

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
  "created_at": "2026-01-15T12:00:00Z",
  "updated_at": "2026-01-15T12:00:00Z"
}
```

`transaction_type` accepts `income`, `expense`, `investment`, or `savings`.
`description` is optional and is returned as `null` when blank. A partial
update may contain any subset of `amount`, `transaction_type`, `category`,
`date`, and `description`; an empty patch is rejected.

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
  -d '{"first_name": "Ana", "timezone": "America/Bogota", "bio": "Keeps a budget."}'
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
  "bio": "Keeps a budget.",
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

## Performance

The implementation keeps expensive work out of request handlers:

- Transaction lists use owner/date indexes and bounded pagination.
- Daily aggregation uses a composite owner/date/type index for filtered sums.
- Dashboard summaries have a unique natural key and an owner/period/date index
  supplied by that constraint, plus a stale-row lookup index.
- Dashboard reads select persisted rows and do not scan transactions.
- Celery work is split by date and period so a transaction change only refreshes
  affected rollups; each task uses database transactions and idempotent upserts.
- Connection reuse is controlled by `DJANGO_DATABASE_CONN_MAX_AGE` and health
  checks are enabled.

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
  settings.

JWT API requests use the `Authorization` header and do not require CSRF
handling. Django session settings remain relevant to the separately served
Django admin surface; do not use those cookies as API credentials.
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
3. Add gateway or DRF throttling for registration, login, and write endpoints;
   rate limits are deployment-specific and are not silently enabled by this MVP.
4. If a separate frontend origin is required, add a narrowly configured CORS
   package such as `django-cors-headers`; the project intentionally does not
   allow arbitrary cross-origin requests by default.
5. Rotate credentials, restrict admin access, and review dependency updates.
6. Keep detailed query logging disabled in production.

## Deployment

### Release sequence

Build and start the runtime image, then run explicit release steps:

```bash
docker compose build
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d web celery_worker celery_beat
```

The image is multi-stage, installs runtime dependencies only, and runs as the
unprivileged UID/GID `10001`. Run migrations as a release job, not from every
web replica.

### Production environment

Set at minimum:

```text
DJANGO_ENVIRONMENT=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<long random secret; keep stable while JWTs are valid>
DJANGO_ALLOWED_HOSTS=api.example.com
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_TRUST_PROXY_HEADERS=true
DJANGO_LOG_QUERIES=false
DATABASE_URL=postgresql://...
REDIS_URL=rediss://...
```

Also configure `DJANGO_SECURE_HSTS_SECONDS` after confirming the entire domain is
HTTPS-only. Keep database and Redis URLs in a secret manager, not in source
control. `docker-compose.yml` is a useful single-host baseline; for a larger
deployment, use managed PostgreSQL/Redis, secret injection, a process
supervisor or orchestrator, and private service networking.

### Database and queue operations

- Schedule daily PostgreSQL backups and test restoration regularly, for example
  with `pg_dump`/`pg_restore` or the managed provider's snapshot service.
- Monitor replication, disk, connection counts, and migration status.
- Run at least one Celery worker and one Beat scheduler (the Compose defaults
  provide both). Scale workers horizontally with `--concurrency`; the configured
  prefetch multiplier of one avoids holding many jobs in one worker.
- Monitor task failures, retries, queue latency, stale summary counts, and
  worker memory. Alert on repeated `OperationalError` or a growing Redis queue.
- Celery task results expire after one day by default; the database summaries,
  not the result backend, are the durable dashboard record.

### Health and observability

- `/healthz` is a dependency-free liveness probe.
- `/readyz` checks PostgreSQL and should be used as the load-balancer readiness
  probe.
- Timestamped application, Django, and Celery logs go to stdout/stderr and can
  be collected by the platform's log agent.
- Use request IDs and centralized log storage at the reverse proxy/platform
  layer; the application error handler deliberately does not expose stack traces
  to clients.

## Development workflow

### Add a bounded context

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
clients.

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
