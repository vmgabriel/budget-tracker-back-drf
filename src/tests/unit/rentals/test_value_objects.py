"""Rentals value-object tests."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.rentals.domain.exceptions import (
    InvalidAddress,
    InvalidPaymentAmount,
    InvalidReading,
)
from apps.rentals.domain.value_objects import (
    Address,
    ApartmentNumber,
    HouseId,
    MonthlyRent,
    PaymentAmount,
    Reading,
    UnitCost,
    UserId,
)

pytestmark = pytest.mark.unit


def test_address_normalizes_whitespace() -> None:
    address = Address(
        street="  123   Main  St ", city=" Springfield ", state=" IL ", country=" US "
    )

    assert address.street == "123 Main St"
    assert address.city == "Springfield"
    with pytest.raises(FrozenInstanceError):
        address.city = "Elsewhere"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [("street", "   "), ("city", ""), ("state", "x" * 101), ("country", "  ")],
)
def test_address_rejects_blank_or_oversized_parts(field: str, value: str) -> None:
    parts = {"street": "Main", "city": "Springfield", "state": "IL", "country": "US"}
    parts[field] = value

    with pytest.raises(InvalidAddress):
        Address(**parts)


def test_apartment_number_is_trimmed_and_limited() -> None:
    assert ApartmentNumber("  4B ").value == "4B"

    with pytest.raises(ValueError, match="cannot be empty"):
        ApartmentNumber("   ")
    with pytest.raises(ValueError, match="20 characters"):
        ApartmentNumber("A" * 21)


def test_reading_accepts_zero_and_two_decimals() -> None:
    assert Reading(Decimal("0")).amount == Decimal("0")
    assert Reading(Decimal("12.34")).amount == Decimal("12.34")


@pytest.mark.parametrize(
    "value",
    [Decimal("-0.01"), Decimal("1.999"), Decimal("1000000.00"), Decimal("NaN")],
)
def test_reading_rejects_invalid_measurements(value: Decimal) -> None:
    with pytest.raises(InvalidReading):
        Reading(value)


def test_monthly_rent_must_be_positive() -> None:
    assert MonthlyRent(Decimal("500.00")).amount == Decimal("500.00")

    with pytest.raises(ValueError, match="greater than zero"):
        MonthlyRent(Decimal("0.00"))
    with pytest.raises(ValueError, match="two decimal places"):
        MonthlyRent(Decimal("10.005"))


def test_payment_amount_validates_strictly() -> None:
    assert PaymentAmount(Decimal("1.00")).amount == Decimal("1.00")

    with pytest.raises(InvalidPaymentAmount):
        PaymentAmount(Decimal("0.00"))
    with pytest.raises(InvalidPaymentAmount):
        PaymentAmount(Decimal("-5"))


def test_unit_cost_allows_zero_and_four_decimals() -> None:
    assert UnitCost(Decimal("0")).amount == Decimal("0")
    assert UnitCost(Decimal("0.1234")).amount == Decimal("0.1234")

    with pytest.raises(ValueError, match="cannot be negative"):
        UnitCost(Decimal("-0.01"))
    with pytest.raises(ValueError, match="four decimal places"):
        UnitCost(Decimal("0.12345"))


def test_ids_require_uuids() -> None:
    with pytest.raises(TypeError):
        HouseId("not-a-uuid")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        UserId(123)  # type: ignore[arg-type]

    value = uuid4()
    assert HouseId(value).value == value
