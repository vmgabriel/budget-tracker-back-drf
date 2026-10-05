"""Rentals repository integration tests against the real database."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from apps.rentals.application.dto import Period
from apps.rentals.domain.entities import House, UtilityReading
from apps.rentals.domain.value_objects import (
    Address,
    ApartmentId,
    ApartmentNumber,
    DocumentId,
    DocumentType,
    HouseId,
    MonthlyRent,
    PaymentStatus,
    Reading,
    UnitCost,
    UserId,
    UtilityType,
)
from apps.rentals.infrastructure.persistence.repositories import (
    DjangoApartmentRepository,
    DjangoDocumentRepository,
    DjangoHouseRepository,
    DjangoPaymentRecordRepository,
    DjangoUtilityReadingRepository,
)
from tests.factories import (
    ApartmentFactory,
    DocumentFactory,
    PaymentRecordFactory,
    UserFactory,
    UtilityReadingFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_house_repository_round_trips_value_objects() -> None:
    owner: Any = UserFactory()
    repository = DjangoHouseRepository()
    now = datetime.now(UTC)
    house = House(
        id=None,
        owner_id=UserId(owner.id),
        name="Oak Villa",
        address=Address("5 Oak Ave", "Portland", "OR", "US"),
        created_at=now,
        updated_at=now,
    )

    saved = repository.save(house)

    fetched = repository.get_by_id(saved.id)  # type: ignore[arg-type]
    assert fetched is not None
    assert fetched.name == "Oak Villa"
    assert fetched.address.street == "5 Oak Ave"
    assert fetched.owner_id == UserId(owner.id)

    listed = repository.get_by_owner_id(UserId(owner.id))
    assert [item.id for item in listed] == [saved.id]

    repository.delete(saved)
    assert repository.get_by_id(saved.id) is None  # type: ignore[arg-type]


def test_apartment_repository_reconstructs_domain_entity() -> None:
    model: Any = ApartmentFactory()
    repository = DjangoApartmentRepository()

    apartment = repository.get_by_id(ApartmentId(model.id))

    assert apartment is not None
    assert apartment.number == ApartmentNumber(model.number)
    assert apartment.monthly_rent == MonthlyRent(model.monthly_rent)
    assert apartment.house_id == HouseId(model.house_id)

    by_house = repository.get_by_house_id(HouseId(model.house_id))
    assert [item.id for item in by_house] == [ApartmentId(model.id)]


def test_document_repository_maps_type_and_description() -> None:
    model: Any = DocumentFactory(document_type="ID_CARD", description=None)
    repository = DjangoDocumentRepository()

    document = repository.get_by_id(DocumentId(model.id))

    assert document is not None
    assert document.document_type is DocumentType.ID_CARD
    assert document.description is None
    assert len(repository.get_by_apartment_id(ApartmentId(model.apartment_id))) == 1


def test_utility_reading_repository_period_filter_and_unique_constraint() -> None:
    apartment: Any = ApartmentFactory()
    UtilityReadingFactory(
        apartment=apartment,
        utility_type="WATER",
        reading_date=date(2026, 1, 15),
    )
    UtilityReadingFactory(
        apartment=apartment,
        utility_type="GAS",
        reading_date=date(2026, 2, 15),
    )
    repository = DjangoUtilityReadingRepository()

    january = repository.get_by_apartment_and_period(
        ApartmentId(apartment.id), Period(year=2026, month=1)
    )
    assert len(january) == 1
    assert january[0].consumption.amount == Decimal("20.50")

    with pytest.raises(IntegrityError), transaction.atomic():
        repository.save(
            UtilityReading(
                id=None,
                apartment_id=ApartmentId(apartment.id),
                utility_type=UtilityType.WATER,
                reading_date=date(2026, 1, 15),
                current_reading=Reading(Decimal("130.00")),
                previous_reading=Reading(Decimal("120.50")),
                consumption=Reading(Decimal("9.50")),
                unit_cost=UnitCost(Decimal("0.5000")),
                total_cost=Decimal("4.75"),
                created_at=datetime.now(UTC),
            )
        )


def test_payment_record_repository_round_trip_and_period() -> None:
    apartment: Any = ApartmentFactory()
    PaymentRecordFactory(
        apartment=apartment, payment_date=date(2026, 1, 5), amount=Decimal("500.00")
    )
    PaymentRecordFactory(
        apartment=apartment,
        payment_date=date(2026, 3, 5),
        amount=Decimal("300.00"),
        status="PARTIAL",
    )
    repository = DjangoPaymentRecordRepository()

    january = repository.get_by_apartment_and_period(
        ApartmentId(apartment.id), Period(year=2026, month=1)
    )
    assert len(january) == 1
    record = january[0]
    assert record.amount.amount == Decimal("500.00")
    assert record.status is PaymentStatus.PAID

    record.status = PaymentStatus.OVERDUE
    updated = repository.update(record)
    assert updated.status is PaymentStatus.OVERDUE
