# Life & Home Utility - AI Agent Instructions

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
- Model it as a new bounded context, not as an extension of `transactions` or
  `rentals`.
- Keep contexts autonomous. A context owns its models, its rules, and its
  endpoints, and reaches other contexts only through explicit application
  ports or its own interface.
- Reuse the shared kernel (`Clock`, value-object patterns, the error
  envelope) instead of duplicating it.
- Share identity through the existing `users` and `profile` contexts; never
  introduce a second notion of "owner".
- Enforce the mandatory four-layer separation below without exception.
- Update `README.md` when the public capabilities or API contract change.

## Tech Stack
- **Backend**: Python 3.12+, Django 5.2, Django REST Framework, PostgreSQL 16, Redis 7.4, Celery 5.5+
- **Tooling**: Hatch (dependency/environment management), Docker & Docker Compose, Makefile, pytest, factory-boy, Ruff, Black, mypy, drf-spectacular (OpenAPI)
- **Authentication**: JWT (djangorestframework-simplejwt) with Bearer tokens
- **Time Handling**: `zoneinfo` (Python stdlib), NEVER `pytz`

## Architecture: Majestic Monolith with Bounded Contexts

### 4-Layer Separation (MANDATORY)
Every bounded context under `src/apps/<module>/` MUST follow this structure:

```
src/apps/<module>/
├── domain/                 # Pure Python; NO Django, DRF, Celery, or DB imports
│   ├── entities.py         # Aggregates and entities (mutable dataclasses)
│   ├── value_objects.py    # Immutable value objects (frozen dataclasses)
│   ├── exceptions.py       # Domain-specific failures
│   ── rules.py            # Optional business rules
├── application/            # Use cases and dependency-inversion ports
│   ├── use_cases/          # One use case per file
│   ├── ports/              # typing.Protocol interfaces (NEVER abc.ABC)
│   ├── config.py           # Module-specific configuration (e.g., PROFILE_DEFAULTS)
│   └── __init__.py         # Public application exports
├── infrastructure/         # Django ORM, adapters, Celery tasks, signals
│   ├── persistence/
│   │   ├── models.py       # Django models
│   │   └── repositories.py # Implements application ports
│   ├── adapters/           # External service adapters
│   ├── tasks.py            # Celery tasks (if applicable)
│   └── signals.py          # Django signals (registered in apps.py ready())
└── interfaces/             # DRF serializers, views, URLs
    ├── views.py
    ├── serializers.py
    ├── urls.py
    └── dependencies.py     # Composition root (wires use cases with dependencies)
```

### Shared Kernel
Generic, stable concepts live in `src/shared/` to avoid duplication across bounded contexts:
- `shared/domain/ports/clock.py` - Clock protocol
- `shared/infrastructure/clock.py` - SystemClock implementation

### Dependency Rule
```
interfaces → application → domain
infrastructure → application ports
```
**Domain and application code NEVER import Django, DRF, Celery, PostgreSQL, or infrastructure modules.**

## Critical Design Patterns

### 1. Value Objects
- Use `@dataclass(frozen=True, slots=True)` for immutability and performance
- Validate in `__post_init__()` and raise domain exceptions
- Examples: `Money`, `Email`, `Timezone`, `Language`, `Currency`

### 2. Entities (Aggregates)
- Use `@dataclass(eq=False, slots=True)` (mutable by design)
- Mutation methods take keyword-only `now: datetime` parameter injected from `Clock` port
- Example: `user.ban(reason, now=clock.now())`, `transaction.update(amount, now=clock.now())`

### 3. Ports (Dependency Inversion)
- Use `typing.Protocol` for structural typing (duck typing)
- NEVER use `abc.ABC` (nominal typing forces inheritance)
- Ports live in `application/ports/` and are implemented in `infrastructure/`

### 4. Time Abstraction
- **NEVER** use `datetime.now()` directly in domain or application layers
- Always inject and use the `Clock` port from `shared.domain.ports.clock`
- Use `zoneinfo` (stdlib) for timezone handling, NEVER `pytz` (deprecated in Django 5.x)

### 5. Configuration
- Module-specific defaults (e.g., `PROFILE_DEFAULTS`) live in `application/config.py`
- Domain layer has NO knowledge of default values (keeps it pure and configurable)

### 6. Use Cases
- One file per use case in `application/use_cases/`
- Export from `application/use_cases/__init__.py`
- Wire dependencies in `interfaces/dependencies.py` (composition root)
- Inject all dependencies via `__init__`, never instantiate internally

### 7. API Errors
All DRF errors use a standardized envelope from `src/config/api.py`:
```json
{
  "error": {
    "code": "validation_error",
    "message": "The request contains invalid data.",
    "details": { "field": ["error message"] }
  },
  "detail": "The request contains invalid data.",
  "field": ["error message"]
}
```

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

Single test example:
```bash
hatch run test:pytest src/tests/unit/users/test_ban_user.py -m unit
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

## Testing Strategy

### Unit Tests (`src/tests/unit/`)
- **NO database**, NO Django imports in domain/application tests
- Mock all external dependencies (repositories, clocks)
- Use `FakeRepository` and `FakeClock` patterns (not `freezegun`)
- Mark with `@pytest.mark.unit`
- Fast execution (< 5 seconds)

### Integration Tests (`src/tests/integration/`)
- Use real database (PostgreSQL in Docker)
- Test Django ORM repositories, DRF views, Celery tasks
- Use `factory-boy` for test data (`UserFactory`, `TransactionFactory`, etc.)
- JWT helpers in `src/tests/factories.py` (`jwt_token_factory`)
- Mark with `@pytest.mark.integration` and `@pytest.mark.django_db(transaction=True)`
- For Celery tasks: use `.apply()` for synchronous testing, `pytest-celery` only for async behavior

### Architecture Tests
- `src/tests/unit/test_architecture.py` enforces domain purity (no framework imports)
- Runs automatically with `make test-unit`

## Development Workflow

### Adding a New Bounded Context
1. Create `src/apps/<module>/{domain,application,infrastructure,interfaces}`
2. Keep entities/value objects pure (no Django imports)
3. Use `@dataclass(frozen=True, slots=True)` for value objects
4. Declare ports with `typing.Protocol`
5. Implement adapters/repositories under `infrastructure`
6. Add serializers, views, and URLs under `interfaces`
7. Aggregate URLs in `src/apps/api/urls.py`
8. Add unit tests for domain/use cases, integration tests for adapters/HTTP
9. Run `make lint`, `make test-unit`, `make test-integration`

### Adding a Celery Task
1. Put task code in `infrastructure/tasks.py`
2. Use application use cases (don't duplicate business logic)
3. Make writes idempotent (use natural keys for upserts)
4. Retry only transient failures (`OperationalError`), bound retries
5. Schedule follow-up work after transaction commits (`transaction.on_commit`)
6. Add tests for task registration, success, idempotency, retries

### Adding a New Field to an Existing Model
1. Update domain entity and value objects (if applicable)
2. Update use cases and commands
3. Update Django model in `infrastructure/persistence/models.py`
4. Update repository mappers (`_to_domain`, `_to_model`)
5. Generate migration: `make makemigrations`
6. Apply migration: `make migrate`
7. Update serializers and views (if field is exposed via API)
8. Update tests

## Git Workflow (NON-NEGOTIABLE)

### No Automatic Git Commits
- **NEVER execute `git commit`, `git add`, `git stash`, `git reset --hard`,
  `git checkout --`, `git revert`, `git rebase`, or any other command that
  writes to the git index, working tree, or history.**
- Also forbidden: creating branches or tags (`git switch -c`, `git tag`),
  amending (`git commit --amend`), staging partial hunks, and running
  `git` through a Makefile target, script, or hook. If a tool offers to
  commit on your behalf, decline.
- The developer (human) is solely responsible for reviewing and committing
  code, and owns the commit message and its description of business value.
- Rationale: the developer needs time to review, test, and understand every
  change before it enters project history. Intermediate snapshots clutter the
  history and obscure the full scope of a feature.

### What to do instead
1. Make the code/documentation/config changes in the working tree.
2. Run the verification suite: `make lint` and `make test` (or
   `make test-unit` / `make test-integration` for a single layer), plus
   `make migrations-check` and `make check` when models or settings changed.
3. Report a summary: files modified, files added, tests added or changed, and
   the verification results.
4. **Stop and wait for explicit developer approval.** Do not treat the task as
   finished, and do not start follow-up work, until it is given.

### Scope
- This rule applies to everything in this repository: application code, domain
  and application layers, migrations, tests, documentation (README, ADRs,
  `AGENTS.md`), and configuration or infrastructure files.
- It applies to all bounded contexts equally, and it applies to purely
  documentation refactors such as this one.
- Read-only git commands (`git status`, `git diff`, `git log`, `git show`) are
  allowed and encouraged, because reporting a diff is part of the summary.
- Ask before running any destructive git operation, even when the change looks
  trivially safe.

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

### README.md
- Main documentation (capabilities, architecture, API reference, deployment)
- Update when adding new modules or changing API contracts

### Architecture Decision Records (ADRs)
- Located in `docs/adr/`
- Use standard format: Status, Context, Decision, Consequences, Alternatives
- Record significant architectural decisions (e.g., JWT auth, pre-computed
  dashboards, scope expansion in ADR-006)

### OpenAPI Schema
- Generated by `drf-spectacular`
- Schema: `http://127.0.0.1:8000/api/schema/`
- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Regenerate with `make schema`

## Current Modules

### Users (`src/apps/users/`)
- Authentication (JWT) and identity
- Custom User model with email-based login; ban/unban functionality

### Profile (`src/apps/profile/`)
- User preferences and localization: timezone, language, currency, date format
- Personal details: bio, avatar
- Auto-provisioned via `post_save` signal
- Configurable defaults in `application/config.py`

### Transactions (`src/apps/transactions/`)
- Financial operations: CRUD for income, expense, investment, and savings
- Owner-scoped

### Dashboard (`src/apps/dashboard/`)
- Pre-computed life/financial summaries (daily, weekly, monthly)
- Celery tasks for async aggregation
- Idempotent tasks with retry logic

### Rentals (`src/apps/rentals/`)
- Property management: houses and apartments
- Document management per apartment (ID cards, leases, certificates)
- Utility meters: readings, consumption, and monthly bills
- Payment tracking: rent payments, status derivation, monthly balance

### Tasks (`src/apps/tasks/`)
- Tasks with priority, hour estimate, due date, and `todo`/`doing`/`done` status
- Goals (macrotasks) grouping tasks; deleting a goal keeps its tasks
- Daily plans: one per user and day, with an hour budget and a full-day conflict
- Overwhelmed-task flag from an injected planning policy (see `application/config.py`)
- LLM evaluation flags reserved for Phase 2 (no LLM integration yet)

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
