"""Optional SQL query logging middleware for local development."""

from collections.abc import Callable

from django.db import connection
from django.http import HttpRequest, HttpResponse


class QueryLoggingMiddleware:
    """Force Django's debug cursor for the duration of each request."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        previous = connection.force_debug_cursor
        connection.force_debug_cursor = True
        try:
            return self.get_response(request)
        finally:
            connection.force_debug_cursor = previous
