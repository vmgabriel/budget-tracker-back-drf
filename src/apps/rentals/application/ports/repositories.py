"""Persistence ports for the rentals context."""

from typing import Protocol

from apps.rentals.application.dto import Period
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
    HouseId,
    PaymentRecordId,
    UserId,
    UtilityReadingId,
)


class HouseRepository(Protocol):
    """Storage operations required by house use cases."""

    def get_by_id(self, house_id: HouseId) -> House | None:
        """Find a house by its identity."""
        ...

    def get_by_owner_id(self, owner_id: UserId) -> list[House]:
        """Return all houses owned by ``owner_id``."""
        ...

    def save(self, house: House) -> House:
        """Persist a new house and return its stored representation."""
        ...

    def update(self, house: House) -> House:
        """Persist changes made to an existing house."""
        ...

    def delete(self, house: House) -> None:
        """Delete an existing house."""
        ...


class ApartmentRepository(Protocol):
    """Storage operations required by apartment use cases."""

    def get_by_id(self, apartment_id: ApartmentId) -> Apartment | None:
        """Find an apartment by its identity."""
        ...

    def get_by_house_id(self, house_id: HouseId) -> list[Apartment]:
        """Return all apartments of one house."""
        ...

    def save(self, apartment: Apartment) -> Apartment:
        """Persist a new apartment and return its stored representation."""
        ...

    def update(self, apartment: Apartment) -> Apartment:
        """Persist changes made to an existing apartment."""
        ...

    def delete(self, apartment: Apartment) -> None:
        """Delete an existing apartment."""
        ...


class DocumentRepository(Protocol):
    """Storage operations required by document use cases."""

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        """Find a document by its identity."""
        ...

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[Document]:
        """Return all documents of one apartment."""
        ...

    def save(self, document: Document) -> Document:
        """Persist a new document and return its stored representation."""
        ...

    def delete(self, document: Document) -> None:
        """Delete an existing document."""
        ...


class UtilityReadingRepository(Protocol):
    """Storage operations required by utility reading use cases."""

    def get_by_id(self, reading_id: UtilityReadingId) -> UtilityReading | None:
        """Find a reading by its identity."""
        ...

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[UtilityReading]:
        """Return every reading recorded for one apartment."""
        ...

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[UtilityReading]:
        """Return the readings of one apartment within a calendar month."""
        ...

    def save(self, reading: UtilityReading) -> UtilityReading:
        """Persist a new reading and return its stored representation."""
        ...


class PaymentRecordRepository(Protocol):
    """Storage operations required by payment tracking use cases."""

    def get_by_id(self, payment_record_id: PaymentRecordId) -> PaymentRecord | None:
        """Find a payment record by its identity."""
        ...

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[PaymentRecord]:
        """Return every payment recorded for one apartment."""
        ...

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[PaymentRecord]:
        """Return the payments of one apartment within a calendar month."""
        ...

    def save(self, record: PaymentRecord) -> PaymentRecord:
        """Persist a new payment record and return its stored representation."""
        ...

    def update(self, record: PaymentRecord) -> PaymentRecord:
        """Persist changes made to an existing payment record."""
        ...
