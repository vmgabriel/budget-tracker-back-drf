"""Shared API query serializers used by paginated endpoints."""

from rest_framework import serializers


class PaginationQuerySerializer(serializers.Serializer):
    """Document and validate the common page query contract."""

    page = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=10_000,
        default=1,
        help_text="One-based page number, from 1 through 10,000.",
    )
    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
        help_text="Number of records per page, from 1 through 100.",
    )


__all__ = ("PaginationQuerySerializer",)
