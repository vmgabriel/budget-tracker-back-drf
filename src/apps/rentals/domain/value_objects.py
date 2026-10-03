"""Immutable value objects for the rentals domain."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from apps.rentals.domain.exceptions import (
    InvalidAddress,
    InvalidPaymentAmount,
    InvalidReading,
)

CENT = Decimal("0.01")
UNIT_COST_STEP = Decimal("0.0001")
MAX_MONEY_AMOUNT = Decimal("99999999.99")
MAX_READING = Decimal("999999.99")


class DocumentType(StrEnum):
    """Categories of documents attached to an apartment."""

    ID_CARD = "ID_CARD"
    LEASE_CONTRACT = "LEASE_CONTRACT"
    EMPLOYMENT_CERTIFICATE = "EMPLOYMENT_CERTIFICATE"
    OTHER = "OTHER"


DOCUMENT_TYPE_CHOICES: tuple[tuple[str, str], ...] = (
    (DocumentType.ID_CARD.value, "ID Card"),
    (DocumentType.LEASE_CONTRACT.value, "Lease Contract"),
    (DocumentType.EMPLOYMENT_CERTIFICATE.value, "Employment Certificate"),
    (DocumentType.OTHER.value, "Other"),
)


class UtilityType(StrEnum):
    """Utilities for which meter readings are tracked."""

    WATER = "WATER"
    ELECTRICITY = "ELECTRICITY"
    GAS = "GAS"


UTILITY_TYPE_CHOICES: tuple[tuple[str, str], ...] = (
    (UtilityType.WATER.value, "Water"),
    (UtilityType.ELECTRICITY.value, "Electricity"),
    (UtilityType.GAS.value, "Gas"),
)


class PaymentStatus(StrEnum):
    """Lifecycle states of a monthly rent payment."""

    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    PAID = "PAID"
    OVERDUE = "OVERDUE"


PAYMENT_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    (PaymentStatus.PENDING.value, "Pending"),
    (PaymentStatus.PARTIAL.value, "Partial"),
    (PaymentStatus.PAID.value, "Paid"),
    (PaymentStatus.OVERDUE.value, "Overdue"),
)


def _require_uuid(value: UUID, label: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{label} must contain a UUID.")


@dataclass(frozen=True, slots=True)
class HouseId:
    """Identity of a persisted house."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "HouseId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ApartmentId:
    """Identity of a persisted apartment."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "ApartmentId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DocumentId:
    """Identity of a persisted document."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "DocumentId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class PaymentRecordId:
    """Identity of a persisted payment record."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "PaymentRecordId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UtilityReadingId:
    """Identity of a persisted utility reading."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "UtilityReadingId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UserId:
    """Reference to a user owned by the users context.

    Duplicated intentionally: bounded contexts never import each other's
    models, so each context keeps its own copy of shared identity concepts.
    """

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "UserId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Address:
    """A validated postal address for a rental property."""

    street: str
    city: str
    state: str
    country: str

    def __post_init__(self) -> None:
        parts = {}
        limits = {"street": 200, "city": 100, "state": 100, "country": 100}
        for field_name, limit in limits.items():
            raw = getattr(self, field_name)
            if not isinstance(raw, str):
                raise InvalidAddress(f"Address {field_name} must be a string.")
            normalized = " ".join(raw.split())
            if not normalized:
                raise InvalidAddress(f"Address {field_name} cannot be empty.")
            if len(normalized) > limit:
                raise InvalidAddress(
                    f"Address {field_name} cannot exceed {limit} characters."
                )
            parts[field_name] = normalized
        object.__setattr__(self, "street", parts["street"])
        object.__setattr__(self, "city", parts["city"])
        object.__setattr__(self, "state", parts["state"])
        object.__setattr__(self, "country", parts["country"])


@dataclass(frozen=True, slots=True)
class ApartmentNumber:
    """A normalized unit identifier within a house."""

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split())
        if not normalized:
            raise ValueError("Apartment number cannot be empty.")
        if len(normalized) > 20:
            raise ValueError("Apartment number cannot exceed 20 characters.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class Reading:
    """A non-negative meter reading with up to 6 integer and 2 decimal digits."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvalidReading("Reading must be a valid decimal value.") from error
        if not amount.is_finite():
            raise InvalidReading("Reading must be finite.")
        if amount < 0:
            raise InvalidReading("Reading cannot be negative.")
        if amount > MAX_READING:
            raise InvalidReading("Reading must not exceed 999999.99.")
        if amount != amount.quantize(CENT):
            raise InvalidReading("Reading must have at most two decimal places.")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class MonthlyRent:
    """A strictly positive monthly rent amount."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError("Rent must be a valid decimal value.") from error
        if not amount.is_finite():
            raise ValueError("Rent must be finite.")
        if amount <= 0:
            raise ValueError("Rent must be greater than zero.")
        if amount > MAX_MONEY_AMOUNT:
            raise ValueError("Rent must not exceed 99999999.99.")
        if amount != amount.quantize(CENT):
            raise ValueError("Rent must have at most two decimal places.")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class PaymentAmount:
    """A strictly positive payment amount."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvalidPaymentAmount(
                "Payment amount must be a valid decimal value."
            ) from error
        if not amount.is_finite():
            raise InvalidPaymentAmount("Payment amount must be finite.")
        if amount <= 0:
            raise InvalidPaymentAmount("Payment amount must be greater than zero.")
        if amount > MAX_MONEY_AMOUNT:
            raise InvalidPaymentAmount("Payment amount must not exceed 99999999.99.")
        if amount != amount.quantize(CENT):
            raise InvalidPaymentAmount(
                "Payment amount must have at most two decimal places."
            )
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class UnitCost:
    """A non-negative cost per unit of a utility, at most 4 decimal places."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError("Unit cost must be a valid decimal value.") from error
        if not amount.is_finite():
            raise ValueError("Unit cost must be finite.")
        if amount < 0:
            raise ValueError("Unit cost cannot be negative.")
        if amount > MAX_MONEY_AMOUNT:
            raise ValueError("Unit cost must not exceed 99999999.99.")
        if amount != amount.quantize(UNIT_COST_STEP):
            raise ValueError("Unit cost must have at most four decimal places.")
        object.__setattr__(self, "amount", amount)
