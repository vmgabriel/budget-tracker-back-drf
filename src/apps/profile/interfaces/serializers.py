"""DRF input and output serializers for the profile context."""

from rest_framework import serializers

from apps.profile.domain.exceptions import (
    InvalidCurrency,
    InvalidLanguage,
    InvalidTimezone,
)
from apps.profile.domain.value_objects import (
    DATE_FORMAT_CHOICES,
    Currency,
    Language,
    Timezone,
)


class ProfileSerializer(serializers.Serializer):
    """Represent a safe profile application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    timezone = serializers.CharField(read_only=True)
    language = serializers.CharField(read_only=True)
    currency = serializers.CharField(read_only=True)
    date_format = serializers.ChoiceField(
        choices=DATE_FORMAT_CHOICES,
        read_only=True,
    )
    avatar_url = serializers.URLField(read_only=True, allow_null=True)
    bio = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class UpdateProfileSerializer(serializers.Serializer):
    """Validate a partial personal-details update.

    Send an empty string for ``avatar_url`` or ``bio`` to clear the current
    value. Omit a field entirely to leave it unchanged.
    """

    first_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
    )
    last_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
    )
    timezone = serializers.CharField(max_length=50, required=False)
    avatar_url = serializers.URLField(
        max_length=200,
        required=False,
        allow_blank=True,
    )
    bio = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
    )

    def validate_timezone(self, value: str) -> str:
        """Reject unknown IANA timezone names early with a per-field error."""
        try:
            return Timezone(value).value
        except InvalidTimezone as error:
            raise serializers.ValidationError(str(error)) from error

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide first_name, last_name, timezone, avatar_url, or bio."
            )
        return attrs


class UpdatePreferencesSerializer(serializers.Serializer):
    """Validate a partial regional-preferences update.

    Omit a field entirely to leave it unchanged.
    """

    language = serializers.CharField(max_length=10, required=False)
    currency = serializers.CharField(max_length=10, required=False)
    date_format = serializers.ChoiceField(
        choices=DATE_FORMAT_CHOICES,
        required=False,
    )

    def validate_language(self, value: str) -> str:
        """Reject non ISO 639-1 codes early with a per-field error."""
        try:
            return Language(value).value
        except InvalidLanguage as error:
            raise serializers.ValidationError(str(error)) from error

    def validate_currency(self, value: str) -> str:
        """Reject non ISO 4217 codes early with a per-field error."""
        try:
            return Currency(value).value
        except InvalidCurrency as error:
            raise serializers.ValidationError(str(error)) from error

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide language, currency, or date_format."
            )
        return attrs
