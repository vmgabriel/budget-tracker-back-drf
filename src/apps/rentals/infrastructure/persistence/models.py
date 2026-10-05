"""Django ORM representations of the rentals aggregates."""

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.rentals.domain.value_objects import (
    DOCUMENT_TYPE_CHOICES,
    PAYMENT_STATUS_CHOICES,
    UTILITY_TYPE_CHOICES,
    DocumentType,
    PaymentStatus,
    UtilityType,
)

VALID_DOCUMENT_TYPES = tuple(item.value for item in DocumentType)
VALID_UTILITY_TYPES = tuple(item.value for item in UtilityType)
VALID_PAYMENT_STATUSES = tuple(item.value for item in PaymentStatus)


class HouseModel(models.Model):
    """A rental property owned by an application user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="houses",
    )
    name = models.CharField(max_length=200)
    street = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="house_name_nonblank",
            ),
        ]
        indexes = [
            models.Index(fields=("owner", "name"), name="house_owner_name_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class ApartmentModel(models.Model):
    """One rentable unit inside a house."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    house = models.ForeignKey(
        HouseModel,
        on_delete=models.CASCADE,
        related_name="apartments",
    )
    number = models.CharField(max_length=20)
    floor = models.IntegerField(default=1)
    monthly_rent = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("number", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(monthly_rent__gt=0),
                name="apartment_rent_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(floor__gte=0),
                name="apartment_floor_nonnegative",
            ),
            models.CheckConstraint(
                condition=~models.Q(number__regex=r"^\s*$"),
                name="apartment_number_nonblank",
            ),
        ]
        indexes = [
            models.Index(fields=("house", "number"), name="apartment_house_number_idx"),
        ]

    def __str__(self) -> str:
        return f"Apartment {self.number}"


class DocumentModel(models.Model):
    """A file associated with an apartment."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    apartment = models.ForeignKey(
        ApartmentModel,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPE_CHOICES,
    )
    file_url = models.URLField(max_length=500)
    description = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-uploaded_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(document_type__in=VALID_DOCUMENT_TYPES),
                name="document_valid_type",
            ),
        ]
        indexes = [
            models.Index(
                fields=("apartment", "document_type"),
                name="document_apartment_type_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document_type} ({self.file_url})"


class UtilityReadingModel(models.Model):
    """One monthly meter reading for one utility of one apartment."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    apartment = models.ForeignKey(
        ApartmentModel,
        on_delete=models.CASCADE,
        related_name="utility_readings",
    )
    utility_type = models.CharField(max_length=20, choices=UTILITY_TYPE_CHOICES)
    reading_date = models.DateField()
    current_reading = models.DecimalField(max_digits=8, decimal_places=2)
    previous_reading = models.DecimalField(max_digits=8, decimal_places=2)
    consumption = models.DecimalField(max_digits=8, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=4)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-reading_date", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("apartment", "utility_type", "reading_date"),
                name="utility_reading_unique_apt_util_date",
            ),
            models.CheckConstraint(
                condition=models.Q(utility_type__in=VALID_UTILITY_TYPES),
                name="utility_reading_valid_type",
            ),
            models.CheckConstraint(
                condition=models.Q(current_reading__gte=models.F("previous_reading")),
                name="utility_reading_current_gte_previous",
            ),
            models.CheckConstraint(
                condition=models.Q(consumption__gte=0),
                name="utility_reading_consumption_nonnegative",
            ),
        ]
        indexes = [
            models.Index(
                fields=("apartment", "utility_type", "-reading_date"),
                name="utility_reading_lookup_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.utility_type} @ {self.reading_date}: {self.consumption}"


class PaymentRecordModel(models.Model):
    """A monthly rent payment made for an apartment."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    apartment = models.ForeignKey(
        ApartmentModel,
        on_delete=models.CASCADE,
        related_name="payment_records",
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-payment_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_PAYMENT_STATUSES),
                name="payment_record_valid_status",
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payment_record_amount_gt_zero",
            ),
        ]
        indexes = [
            models.Index(
                fields=("apartment", "-payment_date"),
                name="payment_apart_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.status}: {self.amount} on {self.payment_date}"
