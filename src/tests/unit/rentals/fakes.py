"""In-memory test doubles for rentals application ports."""

from datetime import UTC, date, datetime
from uuid import uuid4

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

FIXED_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


class FakeHouseRepository:
    """Store house aggregates in memory."""

    def __init__(self) -> None:
        self.houses: dict[HouseId, House] = {}

    def get_by_id(self, house_id: HouseId) -> House | None:
        return self.houses.get(house_id)

    def get_by_owner_id(self, owner_id: UserId) -> list[House]:
        return [house for house in self.houses.values() if house.owner_id == owner_id]

    def save(self, house: House) -> House:
        if house.id is None:
            house.id = HouseId(uuid4())
        self.houses[house.id] = house
        return house

    def update(self, house: House) -> House:
        if house.id is None:
            raise ValueError("Cannot update an unidentified house.")
        self.houses[house.id] = house
        return house

    def delete(self, house: House) -> None:
        if house.id is None:
            raise ValueError("Cannot delete an unidentified house.")
        del self.houses[house.id]


class FakeApartmentRepository:
    """Store apartment aggregates in memory."""

    def __init__(self) -> None:
        self.apartments: dict[ApartmentId, Apartment] = {}

    def get_by_id(self, apartment_id: ApartmentId) -> Apartment | None:
        return self.apartments.get(apartment_id)

    def get_by_house_id(self, house_id: HouseId) -> list[Apartment]:
        return [
            apartment
            for apartment in self.apartments.values()
            if apartment.house_id == house_id
        ]

    def save(self, apartment: Apartment) -> Apartment:
        if apartment.id is None:
            apartment.id = ApartmentId(uuid4())
        self.apartments[apartment.id] = apartment
        return apartment

    def update(self, apartment: Apartment) -> Apartment:
        if apartment.id is None:
            raise ValueError("Cannot update an unidentified apartment.")
        self.apartments[apartment.id] = apartment
        return apartment

    def delete(self, apartment: Apartment) -> None:
        if apartment.id is None:
            raise ValueError("Cannot delete an unidentified apartment.")
        del self.apartments[apartment.id]


class FakeDocumentRepository:
    """Store documents in memory."""

    def __init__(self) -> None:
        self.documents: dict[DocumentId, Document] = {}

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        return self.documents.get(document_id)

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[Document]:
        return [
            document
            for document in self.documents.values()
            if document.apartment_id == apartment_id
        ]

    def save(self, document: Document) -> Document:
        if document.id is None:
            document.id = DocumentId(uuid4())
        self.documents[document.id] = document
        return document

    def delete(self, document: Document) -> None:
        if document.id is None:
            raise ValueError("Cannot delete an unidentified document.")
        del self.documents[document.id]


class FakeUtilityReadingRepository:
    """Store utility readings in memory."""

    def __init__(self) -> None:
        self.readings: dict[UtilityReadingId, UtilityReading] = {}

    def get_by_id(self, reading_id: UtilityReadingId) -> UtilityReading | None:
        return self.readings.get(reading_id)

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[UtilityReading]:
        return [
            reading
            for reading in self.readings.values()
            if reading.apartment_id == apartment_id
        ]

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[UtilityReading]:
        start = period.start_date
        end = period.end_date
        return [
            reading
            for reading in self.readings.values()
            if reading.apartment_id == apartment_id
            and start <= reading.reading_date <= end
        ]

    def save(self, reading: UtilityReading) -> UtilityReading:
        if reading.id is None:
            reading.id = UtilityReadingId(uuid4())
        self.readings[reading.id] = reading
        return reading


class FakePaymentRecordRepository:
    """Store payment records in memory."""

    def __init__(self) -> None:
        self.records: dict[PaymentRecordId, PaymentRecord] = {}

    def get_by_id(self, payment_record_id: PaymentRecordId) -> PaymentRecord | None:
        return self.records.get(payment_record_id)

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[PaymentRecord]:
        return [
            record
            for record in self.records.values()
            if record.apartment_id == apartment_id
        ]

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[PaymentRecord]:
        start = period.start_date
        end = period.end_date
        return [
            record
            for record in self.records.values()
            if record.apartment_id == apartment_id
            and start <= record.payment_date <= end
        ]

    def save(self, record: PaymentRecord) -> PaymentRecord:
        if record.id is None:
            record.id = PaymentRecordId(uuid4())
        self.records[record.id] = record
        return record

    def update(self, record: PaymentRecord) -> PaymentRecord:
        if record.id is None:
            raise ValueError("Cannot update an unidentified payment record.")
        self.records[record.id] = record
        return record
