"""Apartment listing use case."""

from uuid import UUID

from apps.rentals.application.dto import ApartmentDetails, apartment_details
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_house_for_owner
from apps.rentals.domain.value_objects import HouseId


class ListHouseApartments:
    """Return every apartment of a house owned by the requesting user."""

    def __init__(
        self, apartments: ApartmentRepository, houses: HouseRepository
    ) -> None:
        self._apartments = apartments
        self._houses = houses

    def execute(self, house_id: UUID, owner_id: UUID) -> list[ApartmentDetails]:
        require_house_for_owner(self._houses, HouseId(house_id), owner_id)
        apartments = self._apartments.get_by_house_id(HouseId(house_id))
        return [apartment_details(apartment) for apartment in apartments]
