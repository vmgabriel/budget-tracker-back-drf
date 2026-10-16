# DDD & Clean Architecture Rules
- **Domain**: Pure Python. `@dataclass(frozen=True, slots=True)` for VOs. `@dataclass(eq=False, slots=True)` for Entities. NO Django imports.
- **Application**: Use cases take primitive commands. Ports use `typing.Protocol` (NEVER `abc.ABC`). Inject `Clock` for time.
- **Infrastructure**: Django models, repositories implementing ports, Celery tasks.
- **Interfaces**: DRF views (prefer `APIView` or explicit `GenericViewSet` over `ModelViewSet` for owner-scoping control), serializers, URLs.
- **Owner Scoping**: Always return 404 for foreign resources, never 403.
