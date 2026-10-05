"""Django ORM implementations of the rentals repository ports."""

from django.db import transaction as db_transaction

from apps.rentals.application.dto import Period
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    DocumentRepository,
    HouseRepository,
    PaymentRecordRepository,
    UtilityReadingRepository,
)
from apps.rentals.domain.entities import (
    Apartment,
    Document,
    House,
    PaymentRecord,
    UtilityReading,
)
from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    DocumentNotFound,
    HouseNotFound,
    PaymentRecordNotFound,
)
from apps.rentals.domain.value_objects import (
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
from apps.rentals.infrastructure.persistence.models import (
    ApartmentModel,
    DocumentModel,
    HouseModel,
    PaymentRecordModel,
    UtilityReadingModel,
)


class DjangoHouseRepository(HouseRepository):
    """Persist and retrieve houses with the Django ORM."""

    def get_by_id(self, house_id: HouseId) -> House | None:
        model = HouseModel.objects.filter(pk=house_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_owner_id(self, owner_id: UserId) -> list[House]:
        models = HouseModel.objects.filter(owner_id=owner_id.value)
        return [self._to_domain(model) for model in models]

    def save(self, house: House) -> House:
        model = self._to_model(house)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, house: House) -> House:
        if house.id is None:
            raise ValueError("A persisted house must have an identity.")
        model = HouseModel.objects.filter(
            pk=house.id.value,
            owner_id=house.owner_id.value,
        ).first()
        if model is None:
            raise HouseNotFound("House not found.")
        model.name = house.name
        model.street = house.address.street
        model.city = house.address.city
        model.state = house.address.state
        model.country = house.address.country
        with db_transaction.atomic():
            model.save(
                update_fields=(
                    "name",
                    "street",
                    "city",
                    "state",
                    "country",
                    "updated_at",
                )
            )
        return self._to_domain(model)

    def delete(self, house: House) -> None:
        if house.id is None:
            raise ValueError("A persisted house must have an identity.")
        deleted, _ = HouseModel.objects.filter(
            pk=house.id.value,
            owner_id=house.owner_id.value,
        ).delete()
        if not deleted:
            raise HouseNotFound("House not found.")

    @staticmethod
    def _to_model(house: House) -> HouseModel:
        return HouseModel(
            id=house.id.value if house.id is not None else None,
            owner_id=house.owner_id.value,
            name=house.name,
            street=house.address.street,
            city=house.address.city,
            state=house.address.state,
            country=house.address.country,
        )

    @staticmethod
    def _to_domain(model: HouseModel) -> House:
        return House(
            id=HouseId(model.id),
            owner_id=UserId(model.owner_id),
            name=model.name,
            address=Address(
                street=model.street,
                city=model.city,
                state=model.state,
                country=model.country,
            ),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DjangoApartmentRepository(ApartmentRepository):
    """Persist and retrieve apartments with the Django ORM."""

    def get_by_id(self, apartment_id: ApartmentId) -> Apartment | None:
        model = ApartmentModel.objects.filter(pk=apartment_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_house_id(self, house_id: HouseId) -> list[Apartment]:
        models = ApartmentModel.objects.filter(house_id=house_id.value)
        return [self._to_domain(model) for model in models]

    def save(self, apartment: Apartment) -> Apartment:
        model = self._to_model(apartment)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, apartment: Apartment) -> Apartment:
        if apartment.id is None:
            raise ValueError("A persisted apartment must have an identity.")
        model = ApartmentModel.objects.filter(
            pk=apartment.id.value,
            house_id=apartment.house_id.value,
        ).first()
        if model is None:
            raise ApartmentNotFound("Apartment not found.")
        model.number = apartment.number.value
        model.floor = apartment.floor
        model.monthly_rent = apartment.monthly_rent.amount
        with db_transaction.atomic():
            model.save(update_fields=("number", "floor", "monthly_rent", "updated_at"))
        return self._to_domain(model)

    def delete(self, apartment: Apartment) -> None:
        if apartment.id is None:
            raise ValueError("A persisted apartment must have an identity.")
        deleted, _ = ApartmentModel.objects.filter(
            pk=apartment.id.value,
            house_id=apartment.house_id.value,
        ).delete()
        if not deleted:
            raise ApartmentNotFound("Apartment not found.")

    @staticmethod
    def _to_model(apartment: Apartment) -> ApartmentModel:
        return ApartmentModel(
            id=apartment.id.value if apartment.id is not None else None,
            house_id=apartment.house_id.value,
            number=apartment.number.value,
            floor=apartment.floor,
            monthly_rent=apartment.monthly_rent.amount,
        )

    @staticmethod
    def _to_domain(model: ApartmentModel) -> Apartment:
        return Apartment(
            id=ApartmentId(model.id),
            house_id=HouseId(model.house_id),
            number=ApartmentNumber(model.number),
            floor=model.floor,
            monthly_rent=MonthlyRent(model.monthly_rent),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DjangoDocumentRepository(DocumentRepository):
    """Persist and retrieve documents with the Django ORM."""

    def get_by_id(self, document_id: DocumentId) -> Document | None:
        model = DocumentModel.objects.filter(pk=document_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[Document]:
        models = DocumentModel.objects.filter(apartment_id=apartment_id.value)
        return [self._to_domain(model) for model in models]

    def save(self, document: Document) -> Document:
        model = self._to_model(document)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def delete(self, document: Document) -> None:
        if document.id is None:
            raise ValueError("A persisted document must have an identity.")
        deleted, _ = DocumentModel.objects.filter(
            pk=document.id.value,
            apartment_id=document.apartment_id.value,
        ).delete()
        if not deleted:
            raise DocumentNotFound("Document not found.")

    @staticmethod
    def _to_model(document: Document) -> DocumentModel:
        return DocumentModel(
            id=document.id.value if document.id is not None else None,
            apartment_id=document.apartment_id.value,
            document_type=document.document_type.value,
            file_url=document.file_url,
            description=document.description,
        )

    @staticmethod
    def _to_domain(model: DocumentModel) -> Document:
        return Document(
            id=DocumentId(model.id),
            apartment_id=ApartmentId(model.apartment_id),
            document_type=DocumentType(model.document_type),
            file_url=model.file_url,
            description=model.description or None,
            uploaded_at=model.uploaded_at,
        )


class DjangoUtilityReadingRepository(UtilityReadingRepository):
    """Persist and retrieve utility readings with the Django ORM."""

    def get_by_id(self, reading_id: UtilityReadingId) -> UtilityReading | None:
        model = UtilityReadingModel.objects.filter(pk=reading_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[UtilityReading]:
        models = UtilityReadingModel.objects.filter(apartment_id=apartment_id.value)
        return [self._to_domain(model) for model in models]

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[UtilityReading]:
        models = UtilityReadingModel.objects.filter(
            apartment_id=apartment_id.value,
            reading_date__gte=period.start_date,
            reading_date__lte=period.end_date,
        )
        return [self._to_domain(model) for model in models]

    def save(self, reading: UtilityReading) -> UtilityReading:
        model = self._to_model(reading)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    @staticmethod
    def _to_model(reading: UtilityReading) -> UtilityReadingModel:
        return UtilityReadingModel(
            id=reading.id.value if reading.id is not None else None,
            apartment_id=reading.apartment_id.value,
            utility_type=reading.utility_type.value,
            reading_date=reading.reading_date,
            current_reading=reading.current_reading.amount,
            previous_reading=reading.previous_reading.amount,
            consumption=reading.consumption.amount,
            unit_cost=reading.unit_cost.amount,
            total_cost=reading.total_cost,
        )

    @staticmethod
    def _to_domain(model: UtilityReadingModel) -> UtilityReading:
        return UtilityReading(
            id=UtilityReadingId(model.id),
            apartment_id=ApartmentId(model.apartment_id),
            utility_type=UtilityType(model.utility_type),
            reading_date=model.reading_date,
            current_reading=Reading(model.current_reading),
            previous_reading=Reading(model.previous_reading),
            consumption=Reading(model.consumption),
            unit_cost=UnitCost(model.unit_cost),
            total_cost=model.total_cost,
            created_at=model.created_at,
        )


class DjangoPaymentRecordRepository(PaymentRecordRepository):
    """Persist and retrieve payment records with the Django ORM."""

    def get_by_id(self, payment_record_id: PaymentRecordId) -> PaymentRecord | None:
        model = PaymentRecordModel.objects.filter(pk=payment_record_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_apartment_id(self, apartment_id: ApartmentId) -> list[PaymentRecord]:
        models = PaymentRecordModel.objects.filter(apartment_id=apartment_id.value)
        return [self._to_domain(model) for model in models]

    def get_by_apartment_and_period(
        self, apartment_id: ApartmentId, period: Period
    ) -> list[PaymentRecord]:
        models = PaymentRecordModel.objects.filter(
            apartment_id=apartment_id.value,
            payment_date__gte=period.start_date,
            payment_date__lte=period.end_date,
        )
        return [self._to_domain(model) for model in models]

    def save(self, record: PaymentRecord) -> PaymentRecord:
        model = self._to_model(record)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, record: PaymentRecord) -> PaymentRecord:
        if record.id is None:
            raise ValueError("A persisted payment record must have an identity.")
        model = PaymentRecordModel.objects.filter(
            pk=record.id.value,
            apartment_id=record.apartment_id.value,
        ).first()
        if model is None:
            raise PaymentRecordNotFound("Payment record not found.")
        model.payment_date = record.payment_date
        model.amount = record.amount.amount
        model.status = record.status.value
        model.notes = record.notes
        with db_transaction.atomic():
            model.save(update_fields=("payment_date", "amount", "status", "notes"))
        return self._to_domain(model)

    @staticmethod
    def _to_model(record: PaymentRecord) -> PaymentRecordModel:
        return PaymentRecordModel(
            id=record.id.value if record.id is not None else None,
            apartment_id=record.apartment_id.value,
            payment_date=record.payment_date,
            amount=record.amount.amount,
            status=record.status.value,
            notes=record.notes,
        )

    @staticmethod
    def _to_domain(model: PaymentRecordModel) -> PaymentRecord:
        return PaymentRecord(
            id=PaymentRecordId(model.id),
            apartment_id=ApartmentId(model.apartment_id),
            payment_date=model.payment_date,
            amount=PaymentAmount(model.amount),
            status=PaymentStatus(model.status),
            notes=model.notes or None,
            created_at=model.created_at,
        )
