"""DRF input and output serializers for the rentals context."""

from decimal import Decimal

from rest_framework import serializers

from apps.rentals.domain.value_objects import (
    DOCUMENT_TYPE_CHOICES,
    PAYMENT_STATUS_CHOICES,
    UTILITY_TYPE_CHOICES,
)


class CreateHouseSerializer(serializers.Serializer):
    """Validate the fields required to create a house."""

    name = serializers.CharField(max_length=200, trim_whitespace=True)
    street = serializers.CharField(max_length=200, trim_whitespace=True)
    city = serializers.CharField(max_length=100, trim_whitespace=True)
    state = serializers.CharField(max_length=100, trim_whitespace=True)
    country = serializers.CharField(max_length=100, trim_whitespace=True)


class UpdateHouseSerializer(serializers.Serializer):
    """Validate a partial house replacement."""

    name = serializers.CharField(max_length=200, trim_whitespace=True, required=False)
    street = serializers.CharField(max_length=200, trim_whitespace=True, required=False)
    city = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    state = serializers.CharField(max_length=100, trim_whitespace=True, required=False)
    country = serializers.CharField(
        max_length=100, trim_whitespace=True, required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide name, street, city, state, or country."
            )
        return attrs


class CreateApartmentSerializer(serializers.Serializer):
    """Validate the fields required to create an apartment."""

    house_id = serializers.UUIDField()
    number = serializers.CharField(max_length=20, trim_whitespace=True)
    floor = serializers.IntegerField(min_value=0, default=1)
    monthly_rent = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )


class UpdateApartmentSerializer(serializers.Serializer):
    """Validate a partial apartment replacement."""

    number = serializers.CharField(max_length=20, trim_whitespace=True, required=False)
    floor = serializers.IntegerField(min_value=0, required=False)
    monthly_rent = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide number, floor, or monthly_rent.")
        return attrs


class UploadDocumentSerializer(serializers.Serializer):
    """Validate the fields required to attach a document."""

    document_type = serializers.ChoiceField(choices=DOCUMENT_TYPE_CHOICES)
    file_url = serializers.URLField(max_length=500)
    description = serializers.CharField(
        max_length=2000, allow_blank=True, required=False
    )


class RecordUtilityReadingSerializer(serializers.Serializer):
    """Validate the fields required to record a utility reading."""

    utility_type = serializers.ChoiceField(choices=UTILITY_TYPE_CHOICES)
    reading_date = serializers.DateField()
    current_reading = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0")
    )
    previous_reading = serializers.DecimalField(
        max_digits=8, decimal_places=2, min_value=Decimal("0")
    )
    unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=4, min_value=Decimal("0")
    )


class RecordPaymentSerializer(serializers.Serializer):
    """Validate the fields required to record a payment."""

    payment_date = serializers.DateField()
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01")
    )
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)


class UpdatePaymentSerializer(serializers.Serializer):
    """Validate a partial payment replacement."""

    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0.01"), required=False
    )
    status = serializers.ChoiceField(choices=PAYMENT_STATUS_CHOICES, required=False)
    notes = serializers.CharField(max_length=2000, allow_blank=True, required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide amount, status, or notes.")
        return attrs


class HouseDetailsSerializer(serializers.Serializer):
    """Represent a safe house application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    owner_id = serializers.UUIDField(source="owner_id.value", read_only=True)
    name = serializers.CharField(read_only=True)
    street = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    state = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class ApartmentDetailsSerializer(serializers.Serializer):
    """Represent a safe apartment application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    house_id = serializers.UUIDField(source="house_id.value", read_only=True)
    number = serializers.CharField(read_only=True)
    floor = serializers.IntegerField(read_only=True)
    monthly_rent = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class DocumentDetailsSerializer(serializers.Serializer):
    """Represent a safe document application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    apartment_id = serializers.UUIDField(source="apartment_id.value", read_only=True)
    document_type = serializers.ChoiceField(
        choices=DOCUMENT_TYPE_CHOICES, read_only=True
    )
    file_url = serializers.URLField(read_only=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    uploaded_at = serializers.DateTimeField(read_only=True)


class UtilityReadingDetailsSerializer(serializers.Serializer):
    """Represent a safe utility reading application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    apartment_id = serializers.UUIDField(source="apartment_id.value", read_only=True)
    utility_type = serializers.ChoiceField(choices=UTILITY_TYPE_CHOICES, read_only=True)
    reading_date = serializers.DateField(read_only=True)
    current_reading = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )
    previous_reading = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )
    consumption = serializers.DecimalField(
        max_digits=8, decimal_places=2, read_only=True
    )
    unit_cost = serializers.DecimalField(
        max_digits=10, decimal_places=4, read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True
    )
    created_at = serializers.DateTimeField(read_only=True)


class PaymentRecordDetailsSerializer(serializers.Serializer):
    """Represent a safe payment record application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    apartment_id = serializers.UUIDField(source="apartment_id.value", read_only=True)
    payment_date = serializers.DateField(read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    status = serializers.ChoiceField(choices=PAYMENT_STATUS_CHOICES, read_only=True)
    notes = serializers.CharField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class UtilityBillDetailsSerializer(serializers.Serializer):
    """Represent an aggregated utility bill."""

    apartment_id = serializers.UUIDField(source="apartment_id.value", read_only=True)
    utility_type = serializers.ChoiceField(choices=UTILITY_TYPE_CHOICES, read_only=True)
    year = serializers.IntegerField(read_only=True)
    month = serializers.IntegerField(read_only=True)
    total_consumption = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    reading_count = serializers.IntegerField(read_only=True)


class PaymentSummaryDetailsSerializer(serializers.Serializer):
    """Represent an aggregated payment summary."""

    apartment_id = serializers.UUIDField(source="apartment_id.value", read_only=True)
    year = serializers.IntegerField(read_only=True)
    month = serializers.IntegerField(read_only=True)
    total_paid = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    outstanding_balance = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    payment_count = serializers.IntegerField(read_only=True)
