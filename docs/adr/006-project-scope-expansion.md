# ADR-006: Expand project scope to personal life and home management

- **Status:** Accepted
- **Date:** 2026-10-06

## Context

The project was created as a personal budget tracker: a Django REST Framework
API with JWT authentication, owner-scoped financial transactions, and
pre-computed dashboard summaries. Its documented identity, naming, and mental
model were finance-only.

Real usage requirements did not stay inside that boundary. The single owner of
this system also has a home to administer, and needed to keep that side of
their life in the same secure, centralized place: houses and apartments, the
documents that prove ownership or tenancy, utility meters and their bills, and
rent payments with an accurate outstanding balance. That was delivered as the
`rentals` bounded context.

Continuing to describe the system as a "Budget Tracker" is now actively
misleading. It understates the domain, gives new contributors the wrong mental
model, and invites design decisions that optimize for a finance use case when
the real requirement is holistic personal administration. The repository name,
the package metadata, and the documentation all carried the old framing.

At the same time, the existing architecture does not need to change. The
Majestic Monolith with explicit bounded contexts already accommodates
additional, related domains: each one owns its models, rules, and endpoints
without any coupling to the others.

## Decision

We adopt **Life & Home Utility** as the project's name and **personal life and
home management** as its stated scope.

- Documentation, package metadata, and agent instructions describe the system
  as a personal life and home management utility, with finance presented as one
  bounded context among several.
- The Majestic Monolith and the mandatory four-layer Clean Architecture are
  retained unchanged. This is a scope and naming decision, not an
  architectural one; no code logic, layering rule, or dependency direction
  changes.
- New capabilities are admitted only when they serve the centralized life and
  home administration vision, and each is added as its own bounded context
  following the same four layers.
- Contexts stay autonomous and communicate only through explicit application
  ports or their own interfaces. Identity and ownership remain owned by the
  existing `users` and `profile` contexts.
- Infrastructure identifiers that describe the runtime rather than the domain
  (Compose project name, PostgreSQL database and role names, Celery app name,
  environment variable names) are deliberately left unchanged in this change.
  Renaming them is an operational migration and is not required for the domain
  to be understood correctly.

## Consequences

### Positive

- ✅ Documentation, package metadata, and code now describe the same system.
- ✅ The stated scope makes the relevance of future contexts (tasks, habits,
  inventory, maintenance schedules) explicit instead of surprising.
- ✅ Contributors reason about a coherent domain — one owner's life — rather
  than about isolated features.
- ✅ The architecture is validated by real use: `rentals` was added without
  weakening any boundary.

### Negative

- ⚠️ The name is deliberately broader than any single current feature, so the
  README must keep the capability list honest as contexts are added.
- ⚠️ Broader scope invites feature requests that do not belong; the admission
  rule has to be stated explicitly and enforced in review.
- ⚠️ Naming and operational identifiers now differ, which may confuse someone
  looking for a "budget-tracker" database or Compose project. This is accepted
  for now and documented.

### Neutral

- The bounded contexts already shipped are unchanged; only the framing around
  them moved.
- The dominant-context risk shifts rather than disappears: as more contexts
  appear, cross-context consistency (for example a payment in `rentals`
  appearing in `transactions`) must be decided explicitly per feature.

## Alternatives

- **Keep the "Budget Tracker" name:** rejected because it contradicts the
  delivered domain and would mislead every new contributor about where the
  system is going.
- **Split each context into its own service:** rejected for now. Separate
  deployments would add operational and consistency cost that a single owner's
  data does not justify, and the modular monolith already provides the
  boundaries needed to extract a context later if it should grow.
- **A generic "Personal Management Hub" name:** considered and rejected as too
  vague. "Life & Home Utility" states the actual subject matter.
- **Rename infrastructure identifiers at the same time:** deferred. It requires
  a data migration and an operational cutover, which is out of scope for a
  documentation refactor.