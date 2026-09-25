# ADR-002: Session authentication for the first-party client

- **Status:** Superseded by ADR-005
- **Date:** 2026-09-24

> This decision remains historical context. API authentication is now governed
> by [ADR-005](005-use-jwt-authentication.md).

## Context

The MVP is a Django web/API application and already relies on Django sessions,
the user model, password validators, and CSRF middleware. The first release
does not require a separate OAuth or token service.

## Decision

Use Django's opaque, server-side session authentication. Login accepts email
and password, the session cookie is the only credential, and authenticated
unsafe requests must send the CSRF token in `X-CSRFToken`. Passwords are
hashed through Django's configured password hashers.

## Consequences

Browser clients get a simple secure flow and logout can invalidate the session
immediately. API clients must retain cookies and handle CSRF; a future native
or third-party client may need a separate token/OAuth adapter behind the
application authentication port.

## Alternatives

- JWT access tokens: stateless reads, but refresh-token storage, revocation, and
  CSRF/session migration add complexity not needed by the MVP.
- HTTP Basic authentication: unsuitable for browser session semantics and
  password handling.
