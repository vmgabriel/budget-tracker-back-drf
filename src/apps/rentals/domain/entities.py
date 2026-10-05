"""Rental aggregates and entities with their business rules."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    DocumentNotFound,
    InvalidReading,
    PaymentRecordNotFound,
    UtilityReadingNotFound,
)
from apps.rentals.domain.value_objects import (
    CENT,
    Address,
    ApartmentId,
    ApartmentNumber,
    DocumentId,
    DocumentType,
    HouseId,
    MonthlyRent,
    PaymentAmount,
    PaymentRecordId,
    PaymentStatus,
    Reading,
    UnitCost,
    UserId,
    UtilityReadingId,
    UtilityType,
)


@dataclass(eq=False, slots=True)
class House:
    """A rental property owned by a single user."""

    owner_id: UserId
    name: str
    address: Address
    created_at: datetime
    updated_at: datetime
    id: HouseId | None = None
    apartment_ids: list[ApartmentId] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        owner_id: UserId,
        name: str,
        address: Address,
        now: datetime,
    ) -> "House":
        """Create a house after validating aggregate invariants."""
        if not isinstance(owner_id, UserId):
            raise TypeError("House owner must be a UserId.")
        if not isinstance(address, Address):
            raise TypeError("House address must be an Address.")
        normalized = " ".join(str(name).split())
        if not normalized:
            raise ValueError("House name cannot be empty.")
        if len(normalized) > 200:
            raise ValueError("House name cannot exceed 200 characters.")
        cls._require_aware(now)
        return cls(
            id=None,
            owner_id=owner_id,
            name=normalized,
            address=address,
            created_at=now,
            updated_at=now,
        )

    def rename(self, name: str, *, now: datetime) -> None:
        """Change the house display name."""
        normalized = " ".join(str(name).split())
        if not normalized:
            raise ValueError("House name cannot be empty.")
        if len(normalized) > 200:
            raise ValueError("House name cannot exceed 200 characters.")
        self._require_aware(now)
        self.name = normalized
        self.updated_at = now

    def change_address(self, address: Address, *, now: datetime) -> None:
        """Replace the house address."""
        if not isinstance(address, Address):
            raise TypeError("House address must be an Address.")
        self._require_aware(now)
        self.address = address
        self.updated_at = now

    def add_apartment(self, apartment_id: ApartmentId) -> None:
        """Register an apartment id in the house; duplicates are rejected."""
        if not isinstance(apartment_id, ApartmentId):
            raise TypeError("Apartment must be identified by an ApartmentId.")
        if apartment_id in self.apartment_ids:
            raise ValueError("Apartment is already registered on this house.")
        self.apartment_ids.append(apartment_id)

    def remove_apartment(self, apartment_id: ApartmentId) -> None:
        """Unregister an apartment id from the house."""
        if not isinstance(apartment_id, ApartmentId):
            raise TypeError("Apartment must be identified by an ApartmentId.")
        try:
            self.apartment_ids.remove(apartment_id)
        except ValueError as error:
            raise ApartmentNotFound(
                "Apartment does not belong to this house."
            ) from error

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("House timestamps must be timezone-aware.")


@dataclass(eq=False, slots=True)
class Apartment:
    """One rentable unit inside a house."""

    house_id: HouseId
    number: ApartmentNumber
    floor: int
    monthly_rent: MonthlyRent
    created_at: datetime
    updated_at: datetime
    id: ApartmentId | None = None
    document_ids: list[DocumentId] = field(default_factory=list)
    utility_reading_ids: list[UtilityReadingId] = field(default_factory=list)
    payment_record_ids: list[PaymentRecordId] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        house_id: HouseId,
        number: ApartmentNumber,
        floor: int,
        monthly_rent: MonthlyRent,
        now: datetime,
    ) -> "Apartment":
        """Create an apartment after validating aggregate invariants."""
        if not isinstance(house_id, HouseId):
            raise TypeError("Apartment house must be a HouseId.")
        if not isinstance(number, ApartmentNumber):
            raise TypeError("Apartment number must be an ApartmentNumber.")
        if not isinstance(monthly_rent, MonthlyRent):
            raise TypeError("Apartment rent must be a MonthlyRent.")
        if not isinstance(floor, int) or isinstance(floor, bool):
            raise TypeError("Apartment floor must be an integer.")
        if floor < 0:
            raise ValueError("Apartment floor cannot be negative.")
        cls._require_aware(now)
        return cls(
            id=None,
            house_id=house_id,
            number=number,
            floor=floor,
            monthly_rent=monthly_rent,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        number: ApartmentNumber,
        floor: int,
        monthly_rent: MonthlyRent,
        now: datetime,
    ) -> None:
        """Apply a complete validated replacement to the apartment."""
        if not isinstance(number, ApartmentNumber):
            raise TypeError("Apartment number must be an ApartmentNumber.")
        if not isinstance(monthly_rent, MonthlyRent):
            raise TypeError("Apartment rent must be a MonthlyRent.")
        if not isinstance(floor, int) or isinstance(floor, bool):
            raise TypeError("Apartment floor must be an integer.")
        if floor < 0:
            raise ValueError("Apartment floor cannot be negative.")
        self._require_aware(now)
        self.number = number
        self.floor = floor
        self.monthly_rent = monthly_rent
        self.updated_at = now

    def add_document(self, document_id: DocumentId) -> None:
        """Register a document id on the apartment; duplicates are rejected."""
        if not isinstance(document_id, DocumentId):
            raise TypeError("Document must be identified by a DocumentId.")
        if document_id in self.document_ids:
            raise ValueError("Document is already registered on this apartment.")
        self.document_ids.append(document_id)

    def add_utility_reading(self, reading_id: UtilityReadingId) -> None:
        """Register a utility reading id; duplicates are rejected."""
        if not isinstance(reading_id, UtilityReadingId):
            raise TypeError("Reading must be identified by a UtilityReadingId.")
        if reading_id in self.utility_reading_ids:
            raise ValueError("Reading is already registered on this apartment.")
        self.utility_reading_ids.append(reading_id)

    def add_payment_record(self, payment_record_id: PaymentRecordId) -> None:
        """Register a payment record id; duplicates are rejected."""
        if not isinstance(payment_record_id, PaymentRecordId):
            raise TypeError("Payment must be identified by a PaymentRecordId.")
        if payment_record_id in self.payment_record_ids:
            raise ValueError("Payment is already registered on this apartment.")
        self.payment_record_ids.append(payment_record_id)

    def remove_document(self, document_id: DocumentId) -> None:
        """Unregister a document id from the apartment."""
        if not isinstance(document_id, DocumentId):
            raise TypeError("Document must be identified by a DocumentId.")
        try:
            self.document_ids.remove(document_id)
        except ValueError as error:
            raise DocumentNotFound(
                "Document does not belong to this apartment."
            ) from error

    def remove_utility_reading(self, reading_id: UtilityReadingId) -> None:
        """Unregister a utility reading id from the apartment."""
        if not isinstance(reading_id, UtilityReadingId):
            raise TypeError("Reading must be identified by a UtilityReadingId.")
        try:
            self.utility_reading_ids.remove(reading_id)
        except ValueError as error:
            raise UtilityReadingNotFound(
                "Reading does not belong to this apartment."
            ) from error

    def remove_payment_record(self, payment_record_id: PaymentRecordId) -> None:
        """Unregister a payment record id from the apartment."""
        if not isinstance(payment_record_id, PaymentRecordId):
            raise TypeError("Payment must be identified by a PaymentRecordId.")
        try:
            self.payment_record_ids.remove(payment_record_id)
        except ValueError as error:
            raise PaymentRecordNotFound(
                "Payment does not belong to this apartment."
            ) from error

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Apartment timestamps must be timezone-aware.")


@dataclass(eq=False, slots=True)
class Document:
    """A file associated with an apartment."""

    apartment_id: ApartmentId
    document_type: DocumentType
    file_url: str
    description: str | None
    uploaded_at: datetime
    id: DocumentId | None = None

    @classmethod
    def create(
        cls,
        *,
        apartment_id: ApartmentId,
        document_type: DocumentType,
        file_url: str,
        description: str | None,
        now: datetime,
    ) -> "Document":
        """Create a document after validating invariants."""
        if not isinstance(apartment_id, ApartmentId):
            raise TypeError("Document apartment must be an ApartmentId.")
        if not isinstance(document_type, DocumentType):
            raise ValueError("Document type is invalid.")
        normalized_url = str(file_url).strip()
        if not normalized_url:
            raise ValueError("Document file_url cannot be empty.")
        if len(normalized_url) > 500:
            raise ValueError("Document file_url cannot exceed 500 characters.")
        cls._require_aware(now)
        normalized_description = (
            description.strip() or None if description is not None else None
        )
        if normalized_description is not None and len(normalized_description) > 2000:
            raise ValueError("Document description cannot exceed 2000 characters.")
        return cls(
            id=None,
            apartment_id=apartment_id,
            document_type=document_type,
            file_url=normalized_url,
            description=normalized_description,
            uploaded_at=now,
        )

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Document timestamps must be timezone-aware.")


@dataclass(eq=False, slots=True)
class UtilityReading:
    """One monthly meter reading for one utility of one apartment."""

    apartment_id: ApartmentId
    utility_type: UtilityType
    reading_date: date
    current_reading: Reading
    previous_reading: Reading
    consumption: Reading
    unit_cost: UnitCost
    total_cost: Decimal
    created_at: datetime
    id: UtilityReadingId | None = None

    @classmethod
    def create(
        cls,
        *,
        apartment_id: ApartmentId,
        utility_type: UtilityType,
        reading_date: date,
        current_reading: Reading,
        previous_reading: Reading,
        unit_cost: UnitCost,
        now: datetime,
    ) -> "UtilityReading":
        """Create a reading computing consumption and total cost."""
        if not isinstance(apartment_id, ApartmentId):
            raise TypeError("Reading apartment must be an ApartmentId.")
        if not isinstance(utility_type, UtilityType):
            raise ValueError("Utility type is invalid.")
        if not isinstance(current_reading, Reading):
            raise TypeError("Current reading must be a Reading.")
        if not isinstance(previous_reading, Reading):
            raise TypeError("Previous reading must be a Reading.")
        if not isinstance(unit_cost, UnitCost):
            raise TypeError("Unit cost must be a UnitCost.")
        if type(reading_date) is not date:
            raise ValueError("Reading date must be a date.")
        if current_reading.amount < previous_reading.amount:
            raise InvalidReading(
                "Current reading cannot be lower than the previous reading."
            )
        cls._require_aware(now)
        consumption_amount = current_reading.amount - previous_reading.amount
        consumption = Reading(consumption_amount)
        total_cost = (consumption_amount * unit_cost.amount).quantize(CENT)
        return cls(
            id=None,
            apartment_id=apartment_id,
            utility_type=utility_type,
            reading_date=reading_date,
            current_reading=current_reading,
            previous_reading=previous_reading,
            consumption=consumption,
            unit_cost=unit_cost,
            total_cost=total_cost,
            created_at=now,
        )

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Utility reading timestamps must be timezone-aware.")


@dataclass(eq=False, slots=True)
class PaymentRecord:
    """A monthly rent payment made for an apartment."""

    apartment_id: ApartmentId
    payment_date: date
    amount: PaymentAmount
    status: PaymentStatus
    notes: str | None
    created_at: datetime
    id: PaymentRecordId | None = None

    @classmethod
    def create(
        cls,
        *,
        apartment_id: ApartmentId,
        payment_date: date,
        amount: PaymentAmount,
        monthly_rent: MonthlyRent,
        notes: str | None,
        now: datetime,
        status: PaymentStatus | None = None,
    ) -> "PaymentRecord":
        """Create a payment record, auto-calculating status when omitted."""
        if not isinstance(apartment_id, ApartmentId):
            raise TypeError("Payment apartment must be an ApartmentId.")
        if not isinstance(amount, PaymentAmount):
            raise TypeError("Payment amount must be a PaymentAmount.")
        if not isinstance(monthly_rent, MonthlyRent):
            raise TypeError("Monthly rent must be a MonthlyRent.")
        if type(payment_date) is not date:
            raise ValueError("Payment date must be a date.")
        if status is not None and not isinstance(status, PaymentStatus):
            raise ValueError("Payment status is invalid.")
        cls._require_aware(now)
        normalized_notes = notes.strip() or None if notes is not None else None
        if normalized_notes is not None and len(normalized_notes) > 2000:
            raise ValueError("Payment notes cannot exceed 2000 characters.")
        resolved_status = (
            status
            if status is not None
            else cls.calculate_status(amount=amount, monthly_rent=monthly_rent)
        )
        return cls(
            id=None,
            apartment_id=apartment_id,
            payment_date=payment_date,
            amount=amount,
            status=resolved_status,
            notes=normalized_notes,
            created_at=now,
        )

    def refresh_status(self, *, monthly_rent: MonthlyRent) -> None:
        """Recompute the status from the current amount and monthly rent."""
        if not isinstance(monthly_rent, MonthlyRent):
            raise TypeError("Monthly rent must be a MonthlyRent.")
        self.status = self.calculate_status(
            amount=self.amount, monthly_rent=monthly_rent
        )

    def update(
        self,
        *,
        amount: PaymentAmount | None = None,
        status: PaymentStatus | None = None,
        notes: str | None = None,
        recalculate_status: bool = False,
        monthly_rent: MonthlyRent | None = None,
    ) -> None:
        """Apply a partial, validated replacement to the payment record.

        When ``recalculate_status`` is set, the status is derived from the
        (possibly new) amount and ``monthly_rent``; an explicit ``status``
        argument takes precedence.
        """
        if amount is not None and not isinstance(amount, PaymentAmount):
            raise TypeError("Payment amount must be a PaymentAmount.")
        if status is not None and not isinstance(status, PaymentStatus):
            raise ValueError("Payment status is invalid.")
        if amount is not None:
            self.amount = amount
        if notes is not None:
            normalized = notes.strip() or None
            if normalized is not None and len(normalized) > 2000:
                raise ValueError("Payment notes cannot exceed 2000 characters.")
            self.notes = normalized
        if recalculate_status:
            if monthly_rent is None:
                raise ValueError("Monthly rent is required to recalculate status.")
            self.refresh_status(monthly_rent=monthly_rent)
        if status is not None:
            self.status = status

    def mark_overdue(self) -> None:
        """Mark the payment as overdue; fully paid payments cannot lapse."""
        if self.status is PaymentStatus.PAID:
            raise ValueError("A paid payment cannot be marked as overdue.")
        self.status = PaymentStatus.OVERDUE

    @staticmethod
    def calculate_status(
        *, amount: PaymentAmount, monthly_rent: MonthlyRent
    ) -> PaymentStatus:
        """Derive the payment status from the amount vs the monthly rent."""
        if amount.amount >= monthly_rent.amount:
            return PaymentStatus.PAID
        return PaymentStatus.PARTIAL

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Payment timestamps must be timezone-aware.")
