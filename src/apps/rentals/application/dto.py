"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from apps.rentals.domain.entities import (
    Apartment,
    Document,
    House,
    PaymentRecord,
    UtilityReading,
)
from apps.rentals.domain.value_objects import (
    ApartmentId,
    DocumentId,
    DocumentType,
    HouseId,
    PaymentRecordId,
    PaymentStatus,
    UserId,
    UtilityReadingId,
    UtilityType,
)


@dataclass(frozen=True, slots=True)
class Period:
    """A calendar month used to bound bill and payment aggregation."""

    year: int
    month: int

    def __post_init__(self) -> None:
        if not isinstance(self.year, int) or isinstance(self.year, bool):
            raise TypeError("Period year must be an integer.")
        if not isinstance(self.month, int) or isinstance(self.month, bool):
            raise TypeError("Period month must be an integer.")
        if not 1 <= self.month <= 12:
            raise ValueError("Period month must be between 1 and 12.")
        if self.year < 1900 or self.year > 2100:
            raise ValueError("Period year must be between 1900 and 2100.")

    @property
    def start_date(self) -> date:
        """First day of the period."""
        return date(self.year, self.month, 1)

    @property
    def end_date(self) -> date:
        """Last day of the period (inclusive)."""
        if self.month == 12:
            next_month = date(self.year + 1, 1, 1)
        else:
            next_month = date(self.year, self.month + 1, 1)
        return next_month - timedelta(days=1)


@dataclass(frozen=True, slots=True)
class HouseDetails:
    """House data safe to expose through an HTTP interface."""

    id: HouseId
    owner_id: UserId
    name: str
    street: str
    city: str
    state: str
    country: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ApartmentDetails:
    """Apartment data safe to expose through an HTTP interface."""

    id: ApartmentId
    house_id: HouseId
    number: str
    floor: int
    monthly_rent: Decimal
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DocumentDetails:
    """Document data safe to expose through an HTTP interface."""

    id: DocumentId
    apartment_id: ApartmentId
    document_type: DocumentType
    file_url: str
    description: str | None
    uploaded_at: datetime


@dataclass(frozen=True, slots=True)
class UtilityReadingDetails:
    """Utility reading data safe to expose through an HTTP interface."""

    id: UtilityReadingId
    apartment_id: ApartmentId
    utility_type: UtilityType
    reading_date: date
    current_reading: Decimal
    previous_reading: Decimal
    consumption: Decimal
    unit_cost: Decimal
    total_cost: Decimal
    created_at: datetime


@dataclass(frozen=True, slots=True)
class PaymentRecordDetails:
    """Payment record data safe to expose through an HTTP interface."""

    id: PaymentRecordId
    apartment_id: ApartmentId
    payment_date: date
    amount: Decimal
    status: PaymentStatus
    notes: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class UtilityBillDetails:
    """Aggregated consumption and cost for one apartment and utility."""

    apartment_id: ApartmentId
    utility_type: UtilityType
    year: int
    month: int
    total_consumption: Decimal
    total_cost: Decimal
    reading_count: int


@dataclass(frozen=True, slots=True)
class PaymentSummaryDetails:
    """Aggregated payments and outstanding balance for one period."""

    apartment_id: ApartmentId
    year: int
    month: int
    total_paid: Decimal
    outstanding_balance: Decimal
    payment_count: int


def house_details(house: House) -> HouseDetails:
    """Convert a persisted house into a safe result."""
    if house.id is None:
        raise ValueError("A persisted house must have an identity.")
    return HouseDetails(
        id=house.id,
        owner_id=house.owner_id,
        name=house.name,
        street=house.address.street,
        city=house.address.city,
        state=house.address.state,
        country=house.address.country,
        created_at=house.created_at,
        updated_at=house.updated_at,
    )


def apartment_details(apartment: Apartment) -> ApartmentDetails:
    """Convert a persisted apartment into a safe result."""
    if apartment.id is None:
        raise ValueError("A persisted apartment must have an identity.")
    return ApartmentDetails(
        id=apartment.id,
        house_id=apartment.house_id,
        number=apartment.number.value,
        floor=apartment.floor,
        monthly_rent=apartment.monthly_rent.amount,
        created_at=apartment.created_at,
        updated_at=apartment.updated_at,
    )


def document_details(document: Document) -> DocumentDetails:
    """Convert a persisted document into a safe result."""
    if document.id is None:
        raise ValueError("A persisted document must have an identity.")
    return DocumentDetails(
        id=document.id,
        apartment_id=document.apartment_id,
        document_type=document.document_type,
        file_url=document.file_url,
        description=document.description,
        uploaded_at=document.uploaded_at,
    )


def utility_reading_details(reading: UtilityReading) -> UtilityReadingDetails:
    """Convert a persisted utility reading into a safe result."""
    if reading.id is None:
        raise ValueError("A persisted reading must have an identity.")
    return UtilityReadingDetails(
        id=reading.id,
        apartment_id=reading.apartment_id,
        utility_type=reading.utility_type,
        reading_date=reading.reading_date,
        current_reading=reading.current_reading.amount,
        previous_reading=reading.previous_reading.amount,
        consumption=reading.consumption.amount,
        unit_cost=reading.unit_cost.amount,
        total_cost=reading.total_cost,
        created_at=reading.created_at,
    )


def payment_record_details(record: PaymentRecord) -> PaymentRecordDetails:
    """Convert a persisted payment record into a safe result."""
    if record.id is None:
        raise ValueError("A persisted payment record must have an identity.")
    return PaymentRecordDetails(
        id=record.id,
        apartment_id=record.apartment_id,
        payment_date=record.payment_date,
        amount=record.amount.amount,
        status=record.status,
        notes=record.notes,
        created_at=record.created_at,
    )
