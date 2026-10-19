# Project Context (Current State)

## Active Focus
- Current Module: `transactions` — Phase 1 (funding accounts) implemented,
  pending developer review.
- Current Phase: Finance upgrade, step 1 of N. Phase 3 of the previous
  (Production Readiness) track is complete and reviewed.

## Recent Architectural Decisions
- Funding sources live inside the `transactions` bounded context as their own
  `Account` aggregate rather than a new module: the relationship is
  transaction-centric and splitting it would force cross-context joins for
  every spending read.
- `Transaction` owns an optional `account_id` (`SET_NULL`, nullable) so every
  pre-existing transaction stays valid and no backfill is required.
- Transactions expose a flat `account_id` + `account_name` pair instead of a
  nested object. `account_name` is read-model metadata hydrated by the ORM
  adapter (`select_related("account")`), never persisted and never written by
  the domain.
- Per-account writing is link/re-link only. `PATCH` accepts `account_id` but
  rejects `null`, so an account is never silently detached; unlinking is out of
  scope until a later phase asks for it.
- Aggregations deliberately stay out of this phase; the dashboard context is
  untouched and still reads persisted summaries only.

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

## Transactions Phase 1: Accounts & Funding Sources (implemented, pending review)
- Domain: `Account` entity (`id`, `user_id`, `name`, `account_type`,
  `is_active`, timestamps), `AccountId` / `AccountType` value objects,
  `AccountNotFound` / `InvalidAccountType` errors, and
  `Transaction.account_id` (+ `assign_account`).
- Application: `AccountRepository` port, `CreateAccount`,
  `ListUserAccounts`, `GetAccount`, `UpdateTransactionAccount`, and account
  validation inside `CreateTransaction` / `UpdateTransaction`, all resolving
  ownership through `application/scope.py` (foreign accounts surface as 404).
- Infrastructure: `Account` model (UUID PK, owner FK, per-owner active index,
  type/name check constraints), `Transaction.account` FK, and
  `DjangoAccountRepository`.
- Interfaces: `GET|POST /api/v1/transactions/accounts/`,
  `GET /api/v1/transactions/accounts/{id}/`, plus `account_id` /
  `account_name` on every transaction representation.
- Migration: `0003_transaction_funding_accounts.py`.
- Not included on purpose: account rename/deactivate endpoints, pagination for
  accounts, unlinking a transaction, and per-account dashboard rollups.

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
- `transactions`, `dashboard`: Finance & pre-computed summaries. Funding
  accounts (`Account`) are part of `transactions`.
- `rentals`: Properties, documents, utilities, payments.
- `tasks`: Goals, daily plans, local LLM (Ollama) async evaluation.
- `purchases`: Shopping lists, wishlist, tags, soft-delete archival.

## Key Constraints for Current Task
- Reference `.skills/ddd-rules.md` for entity/value object patterns.
- Reference `.skills/testing-rules.md` for test structure.
- DO NOT repeat the full `AGENTS.md`. Assume rules are known.
