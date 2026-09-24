# Budget Tracker

A containerized Python 3.12 / Django 5.2 / Django REST Framework application
built with Domain-Driven Design and Clean Architecture. The base scaffold,
**Step 2 (users/authentication)**, and **Step 3 (transactions)** are implemented;
dashboard aggregation will be added in the subsequent step.

## Architecture

Business code lives under `src/apps/` and is separated into four layers:

```text
src/
├── config/                         # Django, DRF, WSGI/ASGI, and Celery wiring
├── shared/
│   ├── domain/ports/               # Stable framework-independent shared ports
│   └── infrastructure/             # Reusable implementations of shared ports
├── apps/
│   ├── api/                        # Interface-only API v1 URL aggregation
│   ├── users/
│   │   ├── domain/                 # Pure entities, value objects, rules
│   │   ├── application/            # Use cases and dependency-inversion ports
│   │   ├── infrastructure/         # Django ORM repositories and adapters
│   │   └── interfaces/             # DRF controllers and URLs
│   ├── transactions/
│   │   ├── domain/
│   │   ├── application/
│   │   ├── infrastructure/
│   │   └── interfaces/
│   └── dashboard/
│       ├── domain/
│       ├── application/
│       ├── infrastructure/         # Summary repository and Celery tasks
│       └── interfaces/
└── tests/
    ├── unit/                       # Database-free domain/application tests
    └── integration/                # Infrastructure and HTTP tests
```

The dependency direction is `interfaces -> application -> domain`.
Infrastructure implements ports declared by the application layer. Generic,
stable ports and implementations live under `src/shared/`; bounded contexts
must not duplicate them. Domain code will not import Django, Celery,
PostgreSQL, or DRF.

## Technology

- Python 3.12+
- Django 5.2 LTS and Django REST Framework
- PostgreSQL 16
- Redis 7.4 and Celery 5.5+
- Hatch dependency/environment management
- pytest, pytest-django, and factory-boy
- Ruff, Black, and mypy
- Gunicorn in a multi-stage, non-root Docker image

## Prerequisites

Required:

- Docker Engine with the Compose v2 plugin

Optional, for fast local unit tests and quality checks:

- Hatch
- Python 3.12+

Verify Docker Compose:

```bash
docker compose version
```

## Quick start with Docker and Make

```bash
cd budget-tracker
make install             # creates .env from .env.example
make up                  # builds and starts web, worker, PostgreSQL, and Redis
make migrate             # applies migrations after each module is added
make superuser           # optional; create an administrator
```

The API is available at:

- Application: <http://127.0.0.1:8000>
- Liveness endpoint: <http://127.0.0.1:8000/healthz>
- Database readiness endpoint: <http://127.0.0.1:8000/readyz>
- Django admin: <http://127.0.0.1:8000/admin/>

`GET /healthz` is the liveness probe and does not depend on external services;
it returns `{"status": "ok"}`. `GET /readyz` is the readiness probe and returns
the following after a successful database connection:

```json
{"database": "ok", "status": "ok"}
```

### API v1 URL aggregation

All versioned routes are aggregated by `src/apps/api/urls.py` and mounted once
from `config/urls.py` under `/api/v1/`. The aggregator defines the outer
`api_v1` namespace while each context keeps its own `users` or `transactions`
namespace. Existing public paths remain unchanged.

### Users and authentication API

The users context uses Django session authentication:

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register/` | Public | Register with email, full name, and password |
| `POST` | `/api/v1/auth/login/` | Public | Start a session with email and password |
| `POST` | `/api/v1/auth/logout/` | Authenticated | End the current session |
| `GET` | `/api/v1/auth/me/` | Authenticated | Read the current user |
| `GET` | `/api/v1/users/` | Staff only | List users with bounded pagination |
| `GET/PATCH` | `/api/v1/users/{id}/` | Staff only | Read or update email, name, and active state |
| `PATCH` | `/api/v1/users/{id}/plan/` | Staff only | Change `free`, `pro`, or `premium` |

The custom user model uses a UUID primary key, email as its login field, and
`full_name` and `plan` profile fields. The Django admin also exposes user
management. Passwords are hashed through Django's password hasher and are
never represented by the domain or API result objects. Login also sets the
standard CSRF cookie; browser clients sending authenticated unsafe requests
must include the matching `X-CSRFToken` header.

### Transactions API

Transactions are owner-scoped and require authentication. Amounts must be
positive, use no more than two decimal places, and cannot exceed
`9999999999.99`. Dates cannot be in the future. Lists support `page` and
`page_size` query parameters and return the standard count/page envelope.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/transactions/` | List the current user's transactions |
| `POST` | `/api/v1/transactions/` | Create a transaction |
| `GET` | `/api/v1/transactions/{id}/` | Retrieve an owned transaction |
| `PATCH` | `/api/v1/transactions/{id}/` | Update an owned transaction |
| `DELETE` | `/api/v1/transactions/{id}/` | Delete an owned transaction |

Inspect or stop the stack:

```bash
make logs
make stop
make down
```

`make down` preserves PostgreSQL and Redis volumes. If a previously running
Compose stack has stale containers that are no longer attached to the project
network, use `make repair`; it recreates the containers, preserves the volumes,
and applies migrations. Remove the named volumes explicitly only when you
intend to erase local data:

```bash
docker compose down --volumes
```

## Configuration

`.env.example` documents all supported settings. `django-environ` loads `.env`
for host-side Hatch commands, while Compose supplies container-safe database
and Redis URLs.

Important values:

- `DJANGO_SECRET_KEY`: required non-development secret in production
- `DJANGO_DEBUG`: must be `false` in production
- `DJANGO_ALLOWED_HOSTS`: comma-separated host allowlist
- `DATABASE_URL`: host-side PostgreSQL URL used by Hatch
- `DOCKER_DATABASE_URL`: PostgreSQL URL used inside Compose
- `DOCKER_TEST_DATABASE_URL`: isolated PostgreSQL test URL used by the tester
- `TEST_DATABASE_URL`: isolated host-side test database URL
- `REDIS_URL`: host-side Redis/Celery broker URL
- `DOCKER_REDIS_URL`: Redis URL used inside Compose

For production, use a strong secret, HTTPS origins, secure-cookie settings, a
managed PostgreSQL instance, and restricted network access. The image runs as
the unprivileged UID/GID `10001`.

## Make targets

Run `make help` for a concise target list.

| Target | Purpose |
| --- | --- |
| `make install` | Create `.env` without overwriting an existing file |
| `make build` | Build Docker images |
| `make up` / `make down` | Start or stop the stack |
| `make repair` | Recreate containers and apply migrations while preserving volumes |
| `make logs` | Follow web and worker logs |
| `make migrate` | Apply migrations in the web container |
| `make makemigrations` | Generate migrations in the web container |
| `make shell` | Open a Django shell |
| `make superuser` | Create an admin account |
| `make test-unit` | Run database-free tests locally with Hatch |
| `make test-integration` | Run tests in the container test stage against PostgreSQL |
| `make test` | Run both test layers |
| `make lint` | Run Ruff, Black check, and mypy |
| `make format` | Apply Ruff fixes and Black formatting |
| `make check` | Run Django system checks with Hatch |
| `make clean` | Remove local caches and coverage artifacts |

## Hatch environments

`pyproject.toml` defines:

- `default`: project dependencies for local management commands
- `test`: pytest, pytest-django, factory-boy, and related test dependencies
- `lint`: Ruff, Black, and mypy dependencies

Examples:

```bash
hatch env create test
hatch run test:pytest src/tests/unit -m unit
hatch run lint:ruff check .
hatch run default:python manage.py check
```

The unit environment does not need a running database. Integration tests use a
separate database on the Compose PostgreSQL container and never use the local
development database.

## Test database workflow

```bash
make test-integration
```

The `tester` image installs the test extras, waits for PostgreSQL and Redis,
and lets pytest-django create/reuse the dedicated `test_budget_tracker`
database. Tests are marked explicitly as `unit` or `integration`; unknown marks
fail because pytest runs with strict marker validation.

## Production notes

The runtime image installs only runtime dependencies. Test and lint tools are
kept in dedicated build environments. Before a production deployment:

1. Set `DJANGO_ENVIRONMENT=production`, `DJANGO_DEBUG=false`, and secure secret,
   host, proxy, HTTPS, and cookie settings.
2. Run `python manage.py migrate` and `python manage.py collectstatic --noinput`
   as explicit release steps.
3. Run one web process, one or more Celery workers, PostgreSQL, and Redis
   behind appropriate network controls.
4. Route traffic to Gunicorn through a TLS-terminating reverse proxy and keep
   the exposed ports private where possible.
5. Configure database backups and observability; Celery persistence is not a
   substitute for a durable job queue with operational monitoring.
