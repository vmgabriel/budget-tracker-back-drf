"""Shared HTTP API concerns for Django REST Framework.

The exception handler lives in the framework-facing configuration package so
it can be shared by every bounded context without introducing a dependency
from an application or domain module to DRF.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from traceback import format_exception
from typing import Any, cast

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    MethodNotAllowed,
    NotAuthenticated,
    NotFound,
    ParseError,
    PermissionDenied,
    Throttled,
    UnsupportedMediaType,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)


def exception_handler(exc: Exception, context: Mapping[str, Any]) -> Response | None:
    """Return a stable error envelope while retaining DRF compatibility fields.

    The canonical representation is::

        {"error": {"code": "validation_error", "message": "...", "details": ...}}

    Field-level keys such as ``email`` and ``detail`` are also retained at the
    top level. Existing clients can migrate without a flag day, while new
    clients can rely on the versioned ``error`` object.
    """
    response = drf_exception_handler(exc, context)
    if response is None:
        request = context.get("request")
        request_label = _request_label(request)
        logger.error(
            "Unhandled API exception request=%s\n%s",
            request_label,
            "".join(format_exception(type(exc), exc, exc.__traceback__)),
        )
        return Response(
            {
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected server error occurred.",
                    "details": None,
                },
                "detail": "An unexpected server error occurred.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    details = _json_safe(response.data)
    code = _error_code(exc, response.status_code)
    message = _message(details)
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        }
    }
    if isinstance(details, Mapping):
        for key, value in details.items():
            normalized_key = str(key)
            if normalized_key == "detail":
                payload["detail"] = value
            else:
                payload[normalized_key] = value
        payload.setdefault("detail", message)
    else:
        payload["detail"] = message

    response.data = payload
    if response.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        logger.error(
            "API request failed request=%s status=%s code=%s",
            _request_label(context.get("request")),
            response.status_code,
            code,
        )
    return cast(Response, response)


def _error_code(exc: Exception, status_code: int) -> str:
    if isinstance(exc, (ValidationError, DjangoValidationError)):
        return "validation_error"
    if isinstance(exc, NotAuthenticated):
        return "not_authenticated"
    if isinstance(exc, AuthenticationFailed):
        return "authentication_failed"
    if isinstance(exc, (PermissionDenied, DjangoPermissionDenied)):
        return "permission_denied"
    if isinstance(exc, (NotFound, Http404)):
        return "not_found"
    if isinstance(exc, MethodNotAllowed):
        return "method_not_allowed"
    if isinstance(exc, Throttled):
        return "throttled"
    if isinstance(exc, ParseError):
        return "parse_error"
    if isinstance(exc, UnsupportedMediaType):
        return "unsupported_media_type"
    if isinstance(exc, APIException):
        return "api_error"
    return f"http_{status_code}"


def _message(details: Any) -> str:
    if isinstance(details, Mapping):
        detail = details.get("detail")
        if detail:
            return str(detail)
        return "The request contains invalid data."
    if details:
        return "The request contains invalid data."
    return "The request could not be processed."


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def _request_label(request: Any) -> str:
    if request is None:
        return "<unknown>"
    method = getattr(request, "method", "?")
    path = getattr(request, "path", "?")
    return f"{method} {path}"
