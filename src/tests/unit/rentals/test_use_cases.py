"""Rentals use-case tests with in-memory repositories."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.rentals.application.dto import HouseDetails, Period
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.use_cases import (
    CalculateUtilityBill,
    CreateApartment,
    CreateApartmentCommand,
    CreateHouse,
    CreateHouseCommand,
    DeleteHouse,
    GetHouse,
    GetPaymentSummary,
    ListHouseApartments,
    RecordPayment,
    RecordPaymentCommand,
    RecordUtilityReading,
    RecordUtilityReadingCommand,
    UpdatePayment,
    UpdatePaymentCommand,
)
from apps.rentals.domain.exceptions import HouseNotFound

from .fakes import (
    FakeApartmentRepository,
    FakeClock,
    FakeHouseRepository,
    FakePaymentRecordRepository,
    FakeUtilityReadingRepository,
)

pytestmark = pytest.mark.unit


def _create_house(
    houses: FakeHouseRepository, clock: FakeClock, owner_id: UUID
) -> HouseDetails:
    return CreateHouse(houses, clock).execute(
        CreateHouseCommand(
            owner_id=owner_id,
            name="Maple House",
            street="1 Main St",
            city="Springfield",
            state="IL",
            country="US",
        )
    )


def test_get_house_returns_404_for_foreign_owner() -> None:
    houses = FakeHouseRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)

    with pytest.raises(HouseNotFound, match="House not found."):
        GetHouse(houses).execute(house.id.value, uuid4())

    GetHouse(houses).execute(house.id.value, owner_id)


def test_create_apartment_rejects_house_owned_by_someone_else() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)

    with pytest.raises(HouseNotFound):
        CreateApartment(apartments, houses, clock).execute(
            CreateApartmentCommand(
                house_id=house.id.value,
                owner_id=uuid4(),
                number="101",
                floor=1,
                monthly_rent=Decimal("500.00"),
            )
        )


def test_list_house_apartments_hides_foreign_houses() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )

    with pytest.raises(HouseNotFound):
        ListHouseApartments(apartments, houses).execute(house.id.value, uuid4())

    assert (
        len(ListHouseApartments(apartments, houses).execute(house.id.value, owner_id))
        == 1
    )


def test_delete_house_is_owner_scoped() -> None:
    houses = FakeHouseRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)

    with pytest.raises(HouseNotFound):
        DeleteHouse(houses).execute(house.id.value, uuid4())

    DeleteHouse(houses).execute(house.id.value, owner_id)
    assert houses.houses == {}


def test_record_utility_reading_translates_invalid_reading() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    readings = FakeUtilityReadingRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    apartment = CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )

    with pytest.raises(InvalidRentalsInput, match="lower than the previous"):
        RecordUtilityReading(readings, apartments, houses, clock).execute(
            RecordUtilityReadingCommand(
                apartment_id=apartment.id.value,
                owner_id=owner_id,
                utility_type="WATER",
                reading_date=date(2026, 1, 31),
                current_reading=Decimal("50.00"),
                previous_reading=Decimal("100.00"),
                unit_cost=Decimal("0.50"),
            )
        )


def test_record_utility_reading_rejects_duplicate_period_service() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    readings = FakeUtilityReadingRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    apartment = CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )
    command = RecordUtilityReadingCommand(
        apartment_id=apartment.id.value,
        owner_id=owner_id,
        utility_type="WATER",
        reading_date=date(2026, 1, 31),
        current_reading=Decimal("120.00"),
        previous_reading=Decimal("100.00"),
        unit_cost=Decimal("0.50"),
    )
    RecordUtilityReading(readings, apartments, houses, clock).execute(command)

    with pytest.raises(InvalidRentalsInput, match="already exists"):
        RecordUtilityReading(readings, apartments, houses, clock).execute(command)


def test_calculate_utility_bill_aggregates_period() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    readings = FakeUtilityReadingRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    apartment = CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )
    recorder = RecordUtilityReading(readings, apartments, houses, clock)
    recorder.execute(
        RecordUtilityReadingCommand(
            apartment_id=apartment.id.value,
            owner_id=owner_id,
            utility_type="GAS",
            reading_date=date(2026, 1, 10),
            current_reading=Decimal("105.00"),
            previous_reading=Decimal("100.00"),
            unit_cost=Decimal("1.0000"),
        )
    )
    recorder.execute(
        RecordUtilityReadingCommand(
            apartment_id=apartment.id.value,
            owner_id=owner_id,
            utility_type="GAS",
            reading_date=date(2026, 1, 31),
            current_reading=Decimal("120.00"),
            previous_reading=Decimal("105.00"),
            unit_cost=Decimal("1.0000"),
        )
    )

    bill = CalculateUtilityBill(readings, apartments, houses).execute(
        apartment.id.value, owner_id, "GAS", Period(year=2026, month=1)
    )

    assert bill.total_consumption == Decimal("20.00")
    assert bill.total_cost == Decimal("20.00")
    assert bill.reading_count == 2


def test_record_payment_auto_calculates_status_and_summary_aggregates() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    payments = FakePaymentRecordRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    apartment = CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )

    record = RecordPayment(payments, apartments, houses, clock).execute(
        RecordPaymentCommand(
            apartment_id=apartment.id.value,
            owner_id=owner_id,
            payment_date=date(2026, 1, 5),
            amount=Decimal("300.00"),
        )
    )
    assert record.status.value == "PARTIAL"

    summary = GetPaymentSummary(payments, apartments, houses).execute(
        apartment.id.value, owner_id, Period(year=2026, month=1)
    )

    assert summary.total_paid == Decimal("300.00")
    assert summary.outstanding_balance == Decimal("200.00")
    assert summary.payment_count == 1


def test_update_payment_recalculates_status_when_amount_changes() -> None:
    houses = FakeHouseRepository()
    apartments = FakeApartmentRepository()
    payments = FakePaymentRecordRepository()
    clock = FakeClock()
    owner_id = uuid4()
    house = _create_house(houses, clock, owner_id)
    apartment = CreateApartment(apartments, houses, clock).execute(
        CreateApartmentCommand(
            house_id=house.id.value,
            owner_id=owner_id,
            number="101",
            floor=1,
            monthly_rent=Decimal("500.00"),
        )
    )
    record = RecordPayment(payments, apartments, houses, clock).execute(
        RecordPaymentCommand(
            apartment_id=apartment.id.value,
            owner_id=owner_id,
            payment_date=date(2026, 1, 5),
            amount=Decimal("200.00"),
        )
    )

    updated = UpdatePayment(payments, apartments, houses, clock).execute(
        UpdatePaymentCommand(
            payment_record_id=record.id.value,
            owner_id=owner_id,
            amount=Decimal("500.00"),
        )
    )

    assert updated.status.value == "PAID"
