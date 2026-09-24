"""Framework-level HTTP views."""

from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def liveness(request: HttpRequest) -> JsonResponse:
    """Return process liveness without depending on external services."""
    del request
    return JsonResponse({"status": "ok"})


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Report application and database availability without exposing details."""
    del request
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse(
            {"status": "unavailable", "database": "unavailable"}, status=503
        )

    try:
        executor = MigrationExecutor(connection)
        pending_migrations = executor.migration_plan(executor.loader.graph.leaf_nodes())
    except DatabaseError:
        return JsonResponse(
            {"status": "unavailable", "database": "unavailable"}, status=503
        )
    if pending_migrations:
        return JsonResponse(
            {"status": "unavailable", "database": "migrations_pending"}, status=503
        )
    return JsonResponse({"status": "ok", "database": "ok"})
