# ADR-001: Four-layer Clean Architecture

- **Status:** Accepted
- **Date:** 2026-09-24

## Context

The application has business rules that must remain usable without Django,
DRF, Celery, or a database. Persistence and HTTP concerns change more often
than financial invariants.

## Decision

Each bounded context has `domain`, `application`, `infrastructure`, and
`interfaces` layers. Interfaces depend on application use cases; infrastructure
implements application ports; domain code has no framework imports. Ports use
`typing.Protocol`, and time is supplied through the shared `Clock` port.

## Consequences

Business rules are deterministic and unit-testable without a database, while
adapters can be replaced independently. The project has more directories and
composition code than a conventional Django-only layout, and architecture tests
are required to keep the boundary honest.

## Alternatives

- A single Django app with models containing business rules: simpler initially,
  but tightly couples rules to persistence and request frameworks.
- Hexagonal architecture with a single `adapters` directory: viable, but less
  explicit for the users, transactions, and dashboard boundaries.
