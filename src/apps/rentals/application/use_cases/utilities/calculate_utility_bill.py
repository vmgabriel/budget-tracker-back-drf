"""Utility bill calculation use case."""

from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import Period, UtilityBillDetails
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    UtilityReadingRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.value_objects import ApartmentId, UtilityType


class CalculateUtilityBill:
    """Sum consumption and cost for one apartment, utility, and period."""

    def __init__(
        self,
        readings: UtilityReadingRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._readings = readings
        self._apartments = apartments
        self._houses = houses

    def execute(
        self,
        apartment_id: UUID,
        owner_id: UUID,
        utility_type: str,
        period: Period,
    ) -> UtilityBillDetails:
        require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        try:
            utility = UtilityType(utility_type)
            if not isinstance(period, Period):
                raise TypeError("Period must be a Period.")
        except (TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        readings = [
            reading
            for reading in self._readings.get_by_apartment_and_period(
                ApartmentId(apartment_id), period
            )
            if reading.utility_type is utility
        ]
        total_consumption = sum(
            (reading.consumption.amount for reading in readings), Decimal("0")
        )
        total_cost = sum((reading.total_cost for reading in readings), Decimal("0"))
        return UtilityBillDetails(
            apartment_id=ApartmentId(apartment_id),
            utility_type=utility,
            year=period.year,
            month=period.month,
            total_consumption=total_consumption,
            total_cost=total_cost.quantize(Decimal("0.01")),
            reading_count=len(readings),
        )
