"""Framework-facing serializers for shared API metadata."""

from rest_framework import serializers


class ErrorPayloadSerializer(serializers.Serializer):
    """Describe the stable error metadata returned by the API."""

    code = serializers.CharField()
    message = serializers.CharField()
    details = serializers.JSONField(required=False, allow_null=True)


class ErrorResponseSerializer(serializers.Serializer):
    """Describe the canonical API error envelope."""

    error = ErrorPayloadSerializer()
    detail = serializers.CharField(required=False, allow_null=True)


ERROR_RESPONSES: dict[int, type[ErrorResponseSerializer]] = {
    400: ErrorResponseSerializer,
    401: ErrorResponseSerializer,
    403: ErrorResponseSerializer,
    404: ErrorResponseSerializer,
    405: ErrorResponseSerializer,
    429: ErrorResponseSerializer,
    500: ErrorResponseSerializer,
}

__all__ = (
    "ERROR_RESPONSES",
    "ErrorPayloadSerializer",
    "ErrorResponseSerializer",
)
