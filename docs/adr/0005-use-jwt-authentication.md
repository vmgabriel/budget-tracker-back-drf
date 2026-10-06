# ADR-005: Use JWT Authentication Instead of Django Sessions

## Status
Accepted

## Context
The initial implementation used Django Session-based authentication, which:
- Required CSRF token management
- Was difficult to test with Swagger UI
- Was not ideal for mobile clients or API-first architecture
- Required cookie handling in client applications

We needed an authentication method that:
- Works seamlessly with Swagger UI
- Is stateless and scalable
- Supports mobile and web clients equally
- Is industry-standard for REST APIs

Django sessions remain available for the separately served Django admin. They
are not accepted as credentials by the versioned API.

## Decision
We will use JWT (JSON Web Tokens) via `djangorestframework-simplejwt`.

JWT tokens will be:
- Access tokens: 1-hour expiration
- Refresh tokens: 7-day expiration with rotation
- Sent via `Authorization: Bearer <token>` header

The SimpleJWT authentication adapter and token endpoints live in the Django
infrastructure/interface layers. Domain and application code remains
framework-agnostic and knows nothing about HTTP headers or token encoding.
The default deployment does not install the token-blacklist application;
logout is therefore a client-side instruction to discard tokens rather than an
immediate server-side revocation.

## Consequences

### Positive
- ✅ Swagger UI integration works with the OpenAPI HTTP bearer scheme
- ✅ Stateless authentication (no server-side session lookup for API reads)
- ✅ Easy to use with mobile clients (React Native, Flutter)
- ✅ Standard industry practice for REST APIs
- ✅ No CSRF token management required for API writes
- ✅ Better developer experience for API consumers

### Negative
- ⚠️ Tokens cannot be easily revoked before expiration (mitigated by short access token lifetime)
- ⚠️ Slightly more complex token refresh flow
- ⚠️ Larger payload size compared to session IDs
- ⚠️ Rotated refresh tokens are not blacklisted in the default deployment

### Neutral
- Team needs to understand JWT token lifecycle
- Client applications must handle token storage and refresh
- The signing secret must remain stable across replicas and deployments

## Alternatives

- **Keep Django sessions for the API:** rejected because cookie and CSRF
  handling is awkward for mobile clients and Swagger UI.
- **HTTP Basic authentication:** rejected because it sends credentials on
  every request and does not provide a token lifecycle.
- **A separate OAuth/OIDC provider:** deferred until the project needs
  third-party identity federation.
