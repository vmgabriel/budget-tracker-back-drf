"""DRF input and output serializers for the users context."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.domain.value_objects import PLAN_CHOICES


class RegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        max_length=128,
        trim_whitespace=False,
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class UserSerializer(serializers.Serializer):
    id = serializers.UUIDField(source="id.value", read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)
    plan = serializers.ChoiceField(
        choices=PLAN_CHOICES,
        read_only=True,
    )
    is_active = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class AdminUpdateUserSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254, required=False)
    full_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=False,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide full_name or is_active to update."
            )
        return attrs


class ChangeUserPlanSerializer(serializers.Serializer):
    plan = serializers.ChoiceField(choices=PLAN_CHOICES)
