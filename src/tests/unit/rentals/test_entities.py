"""Rentals entity business-rule tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.rentals.domain.entities import (
    Apartment,
    House,
    PaymentRecord,
    UtilityReading,
)
from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    InvalidReading,
    UtilityReadingNotFound,
)
from apps.rentals.domain.value_objects import (
    Address,
    ApartmentId,
    ApartmentNumber,
    HouseId,
    MonthlyRent,
    PaymentAmount,
    PaymentStatus,
    Reading,
    UnitCost,
    UserId,
    UtilityReadingId,
    UtilityType,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 1, 5, 12, tzinfo=UTC)


def _house() -> House:
    return House.create(
        owner_id=UserId(uuid4()),
        name="Maple House",
        address=Address("1 Main St", "Springfield", "IL", "US"),
        now=NOW,
    )


def _apartment() -> Apartment:
    return Apartment.create(
        house_id=HouseId(uuid4()),
        number=ApartmentNumber("101"),
        floor=1,
        monthly_rent=MonthlyRent(Decimal("500.00")),
        now=NOW,
    )


def test_house_registers_and_deregisters_apartments() -> None:
    house = _house()
    apartment_id = ApartmentId(uuid4())

    house.add_apartment(apartment_id)

    assert house.apartment_ids == [apartment_id]
    with pytest.raises(ValueError, match="already registered"):
        house.add_apartment(apartment_id)

    house.remove_apartment(apartment_id)
    assert house.apartment_ids == []
    with pytest.raises(ApartmentNotFound):
        house.remove_apartment(apartment_id)


def test_apartment_registers_children_and_rejects_missing_removals() -> None:
    apartment = _apartment()
    reading_id = UtilityReadingId(uuid4())

    apartment.add_utility_reading(reading_id)
    with pytest.raises(ValueError, match="already registered"):
        apartment.add_utility_reading(reading_id)

    apartment.remove_utility_reading(reading_id)
    with pytest.raises(UtilityReadingNotFound):
        apartment.remove_utility_reading(reading_id)


def test_utility_reading_computes_consumption_and_total() -> None:
    reading = UtilityReading.create(
        apartment_id=ApartmentId(uuid4()),
        utility_type=UtilityType.ELECTRICITY,
        reading_date=date(2026, 1, 31),
        current_reading=Reading(Decimal("120.50")),
        previous_reading=Reading(Decimal("100.00")),
        unit_cost=UnitCost(Decimal("0.50")),
        now=NOW,
    )

    assert reading.consumption.amount == Decimal("20.50")
    assert reading.total_cost == Decimal("10.25")


def test_utility_reading_rejects_reversed_readings() -> None:
    with pytest.raises(InvalidReading, match="lower than the previous"):
        UtilityReading.create(
            apartment_id=ApartmentId(uuid4()),
            utility_type=UtilityType.WATER,
            reading_date=date(2026, 1, 31),
            current_reading=Reading(Decimal("80.00")),
            previous_reading=Reading(Decimal("100.00")),
            unit_cost=UnitCost(Decimal("0.50")),
            now=NOW,
        )


def test_payment_record_derives_status_from_amount_vs_rent() -> None:
    paid = PaymentRecord.create(
        apartment_id=ApartmentId(uuid4()),
        payment_date=date(2026, 1, 5),
        amount=PaymentAmount(Decimal("500.00")),
        monthly_rent=MonthlyRent(Decimal("500.00")),
        notes=None,
        now=NOW,
    )
    partial = PaymentRecord.create(
        apartment_id=ApartmentId(uuid4()),
        payment_date=date(2026, 1, 5),
        amount=PaymentAmount(Decimal("200.00")),
        monthly_rent=MonthlyRent(Decimal("500.00")),
        notes=None,
        now=NOW,
    )

    assert paid.status is PaymentStatus.PAID
    assert partial.status is PaymentStatus.PARTIAL


def test_payment_record_update_recalculates_status() -> None:
    record = PaymentRecord.create(
        apartment_id=ApartmentId(uuid4()),
        payment_date=date(2026, 1, 5),
        amount=PaymentAmount(Decimal("200.00")),
        monthly_rent=MonthlyRent(Decimal("500.00")),
        notes=None,
        now=NOW,
    )
    assert record.status is PaymentStatus.PARTIAL

    record.update(
        amount=PaymentAmount(Decimal("500.00")),
        recalculate_status=True,
        monthly_rent=MonthlyRent(Decimal("500.00")),
    )

    assert record.amount.amount == Decimal("500.00")
    assert record.status is PaymentStatus.PAID


def test_payment_record_update_respects_explicit_status_override() -> None:
    record = PaymentRecord.create(
        apartment_id=ApartmentId(uuid4()),
        payment_date=date(2026, 1, 5),
        amount=PaymentAmount(Decimal("200.00")),
        monthly_rent=MonthlyRent(Decimal("500.00")),
        notes=None,
        now=NOW,
    )

    record.update(status=PaymentStatus.OVERDUE)

    assert record.status is PaymentStatus.OVERDUE

    paid = PaymentRecord.create(
        apartment_id=ApartmentId(uuid4()),
        payment_date=date(2026, 1, 5),
        amount=PaymentAmount(Decimal("500.00")),
        monthly_rent=MonthlyRent(Decimal("500.00")),
        notes=None,
        now=NOW,
    )
    with pytest.raises(ValueError, match="cannot be marked as overdue"):
        paid.mark_overdue()
