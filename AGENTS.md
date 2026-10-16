# Life & Home Utility - AI Agent Instructions

> See `CONTEXT.md` for current state and `.skills/` for specific domain rules
> (`.skills/ddd-rules.md`, `.skills/testing-rules.md`, `.skills/git-rules.md`).

## Project Overview
This is a **Personal Life & Home Management Utility** built as a **Majestic
Monolith** (Modular Monolith with Bounded Contexts) with Django 5.2 and
Domain-Driven Design. Its purpose is to give one owner a single, secure,
centralized place to administer their whole life: identity and preferences,
financial operations, pre-computed summaries, and property/rental
administration. The architecture prioritizes testability, maintainability, and
clear separation of concerns.

## Philosophy
The project started as a personal budget tracker and grew as real needs
surfaced. Do not read that origin as the current limit: **finance is one
bounded context, not the identity of the product.**

Before implementing any new feature, confirm it serves the centralized life
management vision. Planned and anticipated contexts include tasks, habits,
inventory, and maintenance schedules; a request that does not fit a personal
life or home administration scope should be raised rather than absorbed.

When it does fit:
- Model it as a new bounded context, not as an extension of an existing one.
- Keep contexts autonomous. A context owns its models, its rules, and its
  endpoints, and reaches other contexts only through explicit application
  ports or its own interface.
- Reuse the shared kernel (`Clock`, value-object patterns, the error
  envelope) instead of duplicating it.
- Share identity through the existing `users` and `profile` contexts; never
  introduce a second notion of "owner".
- Enforce the mandatory four-layer separation without exception.
- Update `README.md` when the public capabilities or API contract change.

## Tech Stack
- **Backend**: Python 3.12+, Django 5.2, Django REST Framework, PostgreSQL 16, Redis 7.4, Celery 5.5+
- **Tooling**: Hatch (dependency/environment management), Docker & Docker Compose, Makefile, pytest, factory-boy, Ruff, Black, mypy, drf-spectacular (OpenAPI)
- **Authentication**: JWT (djangorestframework-simplejwt) with Bearer tokens
- **Time Handling**: `zoneinfo` (Python stdlib), NEVER `pytz`

## Architecture: Majestic Monolith with Bounded Contexts
Every bounded context under `src/apps/<module>/` uses **four mandatory layers**
— `domain/`, `application/`, `infrastructure/`, `interfaces/`. Entity, value
object, port, and use-case conventions live in `.skills/ddd-rules.md`.

- **Dependency rule**: `interfaces → application → domain`; `infrastructure →
  application ports`. Domain and application code NEVER import Django, DRF,
  Celery, PostgreSQL, or infrastructure modules.
- **Shared kernel**: generic concepts live in `src/shared/` (`Clock` port +
  `SystemClock`); reuse instead of duplicating.
- **Time**: never call `datetime.now()` in domain/application; inject the
  `Clock` port. Use `zoneinfo`, never `pytz`.
- **Configuration**: module defaults live in `application/config.py`; the domain
  has no knowledge of default values.
- **Use cases**: one file per use case, dependencies injected via `__init__`,
  wired in `interfaces/dependencies.py`.
- **API errors**: all DRF errors use the standardized envelope from
  `src/config/api.py`.

## Security & Boundaries (NON-NEGOTIABLE)

### File System Access
- **NEVER** access, read, or search outside the project directory
- Specifically FORBIDDEN: `/root/`, `/usr/`, `/etc/`, `/var/`, `~`, `/home/`
- All file operations must be within `/home/vmgabriel/Documentos/projects/home-manage-utility-drf/`

### Command Execution
- **NEVER** use `sudo` or escalate privileges
- **NEVER** install packages globally (use Hatch environments)
- **NEVER** modify system files or configurations
- All commands must run via `docker compose exec` or `hatch run`

### Authentication & Authorization
- API uses JWT Bearer tokens (`Authorization: Bearer <token>`)
- Django sessions are ONLY for Django admin, NOT for API
- CSRF protection is NOT required for API endpoints (JWT is stateless)
- Protected endpoints must return owner-scoped data (never reveal cross-user resources)

## Common Commands

### Development
```bash
make install              # Create .env if it doesn't exist
make up                   # Build and start all services (web, worker, beat, db, redis)
make down                 # Stop services (preserves volumes)
make logs                 # View logs
make repair               # Recreate containers, preserve volumes, run migrations
```

### Production
`docker-compose.prod.yml` overlays the development stack: no published database
ports, resource limits, named media/static volumes, and the production Gunicorn
config. Never run these targets against a developer stack.

```bash
make prod-release         # Build, migrate, collectstatic, then start the hardened stack
make prod-up              # Start without the release jobs
make prod-logs            # Follow production logs
make prod-down            # Stop (volumes preserved)
make check-deploy         # manage.py check --deploy with the production environment
make backup-db            # Timestamped pg_dump into BACKUP_DIR with retention
```

### Database
```bash
make migrate              # Apply migrations
make makemigrations       # Generate migrations (inside Docker web container)
make migrations-check     # Fail if model changes lack migrations
make backfill-profiles    # Create profiles for existing users (idempotent)
```

### Testing
```bash
make test-unit            # Fast, DB-free tests (hatch run test:pytest src/tests/unit -m unit)
make test-integration     # Tests with DB and Celery (Docker tester container)
make test                 # Run both test layers
```

### Code Quality
```bash
make lint                 # Ruff check + black --check + mypy (run before considering work done)
make format               # Apply Ruff fixes and Black formatting
make check                # Django system checks
make schema               # Validate and generate OpenAPI schema
```

### JWT Tokens
```bash
make token                # Generate JWT token for a user
make refresh-token        # Refresh a JWT token
```

### Production validation
Production is opt-in through `DJANGO_ENVIRONMENT=production`; there is no separate
settings module. Changes to security defaults must keep `manage.py check --deploy`
clean and must not break local or test environments.

The startup guards in `src/config/validators.py` (secret strength, host
allowlist, `DEBUG`, query logging) raise `ImproperlyConfigured` at import time and
are unit-tested; keep them that way rather than moving the checks into views.

## Testing
Structure, markers, and the no-real-LLM rule live in `.skills/testing-rules.md`.
`src/tests/unit/test_architecture.py` enforces domain purity (no framework
imports) and runs with `make test-unit`.

## Development Workflow

### Adding a New Bounded Context
Create `src/apps/<module>/{domain,application,infrastructure,interfaces}` and
follow `.skills/ddd-rules.md` (pure domain, `typing.Protocol` ports, dataclass
rules). Add serializers, views, and URLs under `interfaces`, aggregate URLs in
`src/apps/api/urls.py`, and cover the layers per `.skills/testing-rules.md`.

### Adding a Celery Task
Put task code in `infrastructure/tasks.py` and call application use cases rather
than duplicating business logic. Make writes idempotent (natural keys for
upserts), retry only transient failures (`OperationalError`) with bounded
retries, and schedule follow-up work with `transaction.on_commit`. Test
registration, success, idempotency, and retries.

### Adding a Field to an Existing Model
Update the domain entity/value objects, use cases, the Django model, and the
repository mappers (`_to_domain`, `_to_model`). Run `make makemigrations` and
`make migrate`, then update serializers/views and tests.

## Git Workflow (NON-NEGOTIABLE)
Full rules live in `.skills/git-rules.md`. In short: **NEVER** run `git commit`,
`git add`, `git stash`, `git reset --hard`, `git checkout --`, `git revert`,
`git rebase`, branch/tag creation, or any other command that writes to the git
index, working tree, or history. The developer owns and reviews every commit.

After finishing work: run `make lint` and `make test` (plus `make
migrations-check` and `make check` when models or settings changed), report the
summary of files/tests/verification, then **stop and wait for explicit developer
approval.** Do not start follow-up work until it is given.

## Gotchas & Common Pitfalls

### DRF Permissions
- `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` in `config/settings.py` is only a fallback
- Every protected view sets its own `permission_classes` tuple (overrides defaults)
- **Security changes must be applied to each view's `permission_classes`**, not just settings

### Custom User Model
- `AUTH_USER_MODEL` is `apps.users.User` (email-based, `username = None`)
- JWT access tokens expire in 1 hour, refresh tokens rotate every 7 days
- Logout is client-side (tokens are stateless, no blacklist in MVP)

### Owner Scoping
- Protected HTTP endpoints MUST return owner-scoped data
- Transactions and dashboard summaries are NEVER aggregated on the request path
- Summaries come from pre-computed Celery tasks (read-only in views)

### Django Signals
- Register signals in `apps.py` `ready()` method, NOT in `__init__.py` (avoids circular imports)
- Use `dispatch_uid` to prevent duplicate signal registration
- Guard with `if created:` for `post_save` signals

### Celery Tasks
- Use `@shared_task` decorator
- Make tasks idempotent (safe to retry)
- Use `transaction.on_commit()` to schedule tasks after DB commit
- Tasks use ISO date strings and UUID strings at broker boundary

### API URL Structure
- All versioned routes aggregated in `src/apps/api/urls.py` and mounted under `/api/v1/`
- Keep URLs minimal and RESTful (no duplicates, no "legacy" aliases)
- Use consistent naming (hyphens, not underscores)

## Documentation
- `README.md`: capabilities, architecture, API reference, deployment; update when
  the public capabilities or API contract change.
- ADRs live in `docs/adr/` (Status, Context, Decision, Consequences, Alternatives).
- OpenAPI schema via drf-spectacular (`make schema`): `/api/schema/`, `/api/docs/`.

## Success Criteria for Any Change
Before considering work complete:
- [ ] `make lint` passes (Ruff, Black, mypy)
- [ ] `make test-unit` passes
- [ ] `make test-integration` passes (if applicable)
- [ ] `make migrations-check` passes (if models changed)
- [ ] Domain layer has no framework imports
- [ ] All new code has tests (unit for domain/app, integration for infra/interfaces)
- [ ] README updated (if API changed)
- [ ] New feature fits the centralized life/home management vision and lives in its own bounded context
- [ ] No git write command was executed (`git add`, `git commit`, branch/tag creation, history rewrites)
- [ ] No hardcoded values in domain (use `application/config.py` for defaults)
- [ ] Time handling uses `Clock` port (no `datetime.now()` in domain/app)
