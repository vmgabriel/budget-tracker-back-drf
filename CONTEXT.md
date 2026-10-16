# Project Context (Current State)

## Active Focus
- Current Module: `purchases` (Backend complete, Frontend BFF integration in progress)
- Current Phase: Production Readiness (Phase 3: Observability, CI/CD, Backups) — **complete**, pending developer review.

## Recent Architectural Decisions
- Single `config/settings.py` with `DJANGO_ENVIRONMENT` opt-in (no base/prod split).
- `connect_timeout=5` applied ONLY in production settings (causes test flakiness in Docker).
- Rate limiting applied to auth endpoints (`LoginRateThrottle`, `RegisterRateThrottle`).
- Structured JSON logging via the hand-rolled `JsonLogFormatter` in
  `shared/infrastructure/logging.py`. It is stdlib-only on purpose (no
  `python-json-logger` dependency) and emits `timestamp`, `level`, `logger`,
  `service`, `message`, and the ambient request context. The format is
  env-driven (`DJANGO_LOG_FORMAT`) and pinned to `json` by the production stack.
- `RequestIdMiddleware` is the outermost middleware: it takes or mints
  `X-Request-ID`, binds it to a `ContextVar` so every record emitted while
  handling the request carries it, and returns it on the response (exposed via
  CORS). The per-request access line is gated by `DJANGO_LOG_REQUESTS`.
- Backups are operational scripts, not application code: `scripts/backup_db.sh`
  (timestamped custom-format dump, verified with `pg_restore --list`, 7-day
  retention) and `scripts/restore_db.sh` (validates the archive, dry-run by
  default in spirit, confirms the target name before dropping anything).
  `scripts/backup_loop.sh` drives the Compose `backup` sidecar (profile
  `backup`) so the schedule travels with the stack.
- CI (`.github/workflows/ci.yml`) gates every PR and push to `main` with three
  jobs: `lint` (`make lint`), `test` (`make test`), and `production`
  (`make schema` + `make check-deploy` against a production-shaped `.env`).

## Phase 3 Deliverables (done)
- Structured JSON logging and request-id correlation, with unit tests for the
  formatter/middleware and integration tests over real HTTP.
- `scripts/backup_db.sh`, `scripts/backup_loop.sh`, `scripts/restore_db.sh`;
  `make backup-db` and `make restore-db` targets.
- CI runs lint, the full test suite, the OpenAPI schema validation, and
  Django's deployment checks.
- README updated: observability, backup/restore procedures, CI job table, and
  the logging/backup environment variables.

## Operational Notes
- `pg_restore` must match the server's major version: run restores inside the
  `postgres:16-alpine` container, whose client matches. A mismatched client
  either refuses the archive (`unsupported version`) or emits settings the
  server rejects.
- Backup and restore scripts export the libpq `PG*` variables; without the
  export, `pg_dump`/`pg_restore` silently fall back to a local socket and no
  password.

## Module Map (High Level)
- `users`, `profile`: Identity & localization.
- `transactions`, `dashboard`: Finance & pre-computed summaries.
- `rentals`: Properties, documents, utilities, payments.
- `tasks`: Goals, daily plans, local LLM (Ollama) async evaluation.
- `purchases`: Shopping lists, wishlist, tags, soft-delete archival.

## Key Constraints for Current Task
- Reference `.skills/ddd-rules.md` for entity/value object patterns.
- Reference `.skills/testing-rules.md` for test structure.
- DO NOT repeat the full `AGENTS.md`. Assume rules are known.
