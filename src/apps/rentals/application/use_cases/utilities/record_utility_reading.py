"""Utility reading recording use case."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import (
    Period,
    UtilityReadingDetails,
    utility_reading_details,
)
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    UtilityReadingRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.entities import UtilityReading
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import (
    ApartmentId,
    Reading,
    UnitCost,
    UtilityType,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class RecordUtilityReadingCommand:
    """Input required to record a monthly utility reading."""

    apartment_id: UUID
    owner_id: UUID
    utility_type: str
    reading_date: date
    current_reading: Decimal
    previous_reading: Decimal
    unit_cost: Decimal


class RecordUtilityReading:
    """Record a reading, computing consumption and total cost."""

    def __init__(
        self,
        readings: UtilityReadingRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
        clock: Clock,
    ) -> None:
        self._readings = readings
        self._apartments = apartments
        self._houses = houses
        self._clock = clock

    def execute(self, command: RecordUtilityReadingCommand) -> UtilityReadingDetails:
        require_apartment_for_owner(
            self._apartments,
            self._houses,
            ApartmentId(command.apartment_id),
            command.owner_id,
        )
        try:
            utility_type = UtilityType(command.utility_type)
        except ValueError as error:
            raise InvalidRentalsInput(str(error)) from error

        period = Period(
            year=command.reading_date.year, month=command.reading_date.month
        )
        duplicates = self._readings.get_by_apartment_and_period(
            ApartmentId(command.apartment_id), period
        )
        if any(
            duplicate.utility_type is utility_type
            and duplicate.reading_date == command.reading_date
            for duplicate in duplicates
        ):
            raise InvalidRentalsInput(
                "A reading for this utility and date already exists."
            )

        try:
            reading = UtilityReading.create(
                apartment_id=ApartmentId(command.apartment_id),
                utility_type=utility_type,
                reading_date=command.reading_date,
                current_reading=Reading(command.current_reading),
                previous_reading=Reading(command.previous_reading),
                unit_cost=UnitCost(command.unit_cost),
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return utility_reading_details(self._readings.save(reading))
