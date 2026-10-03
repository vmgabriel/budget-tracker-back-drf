"""Apartment deletion use case."""

from uuid import UUID

from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.value_objects import ApartmentId


class DeleteApartment:
    """Delete an apartment only when its house belongs to the requesting user."""

    def __init__(
        self, apartments: ApartmentRepository, houses: HouseRepository
    ) -> None:
        self._apartments = apartments
        self._houses = houses

    def execute(self, apartment_id: UUID, owner_id: UUID) -> None:
        apartment = require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        self._apartments.delete(apartment)
