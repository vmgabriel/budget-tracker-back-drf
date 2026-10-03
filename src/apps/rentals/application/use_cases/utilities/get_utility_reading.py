"""Single utility reading query use case."""

from uuid import UUID

from apps.rentals.application.dto import (
    UtilityReadingDetails,
    utility_reading_details,
)
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    UtilityReadingRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    UtilityReadingNotFound,
)
from apps.rentals.domain.value_objects import UtilityReadingId


class GetUtilityReading:
    """Return a reading only when its apartment belongs to the requesting user."""

    def __init__(
        self,
        readings: UtilityReadingRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._readings = readings
        self._apartments = apartments
        self._houses = houses

    def execute(self, reading_id: UUID, owner_id: UUID) -> UtilityReadingDetails:
        reading = self._readings.get_by_id(UtilityReadingId(reading_id))
        if reading is None:
            raise UtilityReadingNotFound("Utility reading not found.")
        try:
            require_apartment_for_owner(
                self._apartments, self._houses, reading.apartment_id, owner_id
            )
        except ApartmentNotFound as error:
            raise UtilityReadingNotFound("Utility reading not found.") from error
        return utility_reading_details(reading)
