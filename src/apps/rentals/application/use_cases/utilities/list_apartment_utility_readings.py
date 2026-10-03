"""Utility reading listing use case."""

from datetime import date
from uuid import UUID

from apps.rentals.application.dto import (
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
from apps.rentals.domain.value_objects import ApartmentId, UtilityType


class ListApartmentUtilityReadings:
    """Return readings of an apartment filtered by utility and date range."""

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
        *,
        utility_type: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[UtilityReadingDetails]:
        require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidRentalsInput("start_date must not be after end_date.")
        try:
            type_filter = (
                UtilityType(utility_type) if utility_type is not None else None
            )
        except ValueError as error:
            raise InvalidRentalsInput(str(error)) from error
        readings = self._readings.get_by_apartment_id(ApartmentId(apartment_id))
        if type_filter is not None:
            readings = [r for r in readings if r.utility_type is type_filter]
        if start_date is not None:
            readings = [r for r in readings if r.reading_date >= start_date]
        if end_date is not None:
            readings = [r for r in readings if r.reading_date <= end_date]
        return [utility_reading_details(reading) for reading in readings]
