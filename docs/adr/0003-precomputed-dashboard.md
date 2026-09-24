# ADR-003: Pre-compute dashboard summaries

- **Status:** Accepted
- **Date:** 2026-09-24

## Context

Dashboard reads are frequent, while transaction aggregation becomes more
expensive as history grows. A transaction write must also cause the current
day, week, and month views to converge without making the HTTP request wait for
Celery.

## Decision

Persist daily, weekly, and monthly `DashboardSummary` rows with a unique
`(user, period, date)` key. Celery calculates daily totals from indexed
transactions, rolls them up through weeks and months, and marks affected rows
stale before regeneration. Dashboard read use cases only load persisted rows.

## Consequences

Reads have predictable query cost and can explicitly report stale or missing
data. The system is eventually consistent, workers must be monitored, and
month-boundary logic requires careful tests. Duplicate task delivery is safe
through invalidation plus idempotent upserts.

## Alternatives

- Calculate all periods in the request: immediately consistent but increasingly
  expensive and prone to read-time load spikes.
- Cache only response fragments: simpler invalidation, but no durable, auditable
  summary record and weaker query behavior.
