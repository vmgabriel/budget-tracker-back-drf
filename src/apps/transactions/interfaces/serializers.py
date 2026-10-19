"""DRF input and output serializers for the transactions context."""

from decimal import Decimal

from rest_framework import serializers

from apps.transactions.domain.value_objects import (
    ACCOUNT_TYPE_CHOICES,
    TRANSACTION_CHOICES,
)


class CreateAccountSerializer(serializers.Serializer):
    """Validate the fields required to create a funding account."""

    name = serializers.CharField(max_length=100, allow_blank=False)
    account_type = serializers.ChoiceField(choices=ACCOUNT_TYPE_CHOICES)


class AccountSerializer(serializers.Serializer):
    """Represent a safe funding-account application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(read_only=True)
    account_type = serializers.ChoiceField(
        choices=ACCOUNT_TYPE_CHOICES,
        read_only=True,
    )
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CreateTransactionSerializer(serializers.Serializer):
    """Validate the fields required to create a transaction."""

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    transaction_type = serializers.ChoiceField(choices=TRANSACTION_CHOICES)
    category = serializers.CharField(max_length=100)
    date = serializers.DateField()
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )
    account_id = serializers.UUIDField(required=False)


class UpdateTransactionSerializer(serializers.Serializer):
    """Validate a partial transaction replacement."""

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
    )
    transaction_type = serializers.ChoiceField(
        choices=TRANSACTION_CHOICES,
        required=False,
    )
    category = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
    )
    date = serializers.DateField(required=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )
    # Linking only: ``null`` is rejected so an existing account is never
    # silently detached.
    account_id = serializers.UUIDField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide amount, transaction_type, category, date, description, "
                "or account_id."
            )
        return attrs


class TransactionSerializer(serializers.Serializer):
    """Represent a safe transaction application result.

    ``account_id`` and ``account_name`` are flat on purpose: the BFF charts
    group transactions per funding source without de-referencing a nested
    object.
    """

    id = serializers.UUIDField(source="id.value", read_only=True)
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True,
    )
    transaction_type = serializers.ChoiceField(
        choices=TRANSACTION_CHOICES,
        read_only=True,
    )
    category = serializers.CharField(read_only=True)
    date = serializers.DateField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    account_id = serializers.UUIDField(
        source="account_id.value",
        read_only=True,
        allow_null=True,
    )
    account_name = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class TransactionPageSerializer(serializers.Serializer):
    """Represent a bounded page of safe transaction results."""

    count = serializers.IntegerField(read_only=True)
    page = serializers.IntegerField(read_only=True)
    page_size = serializers.IntegerField(read_only=True)
    results = TransactionSerializer(many=True, read_only=True)


class AccountListSerializer(serializers.Serializer):
    """Represent the owner's active funding accounts."""

    count = serializers.IntegerField(read_only=True)
    results = AccountSerializer(many=True, read_only=True)
