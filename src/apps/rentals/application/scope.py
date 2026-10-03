"""Owner-scoping helpers shared by rentals use cases."""

from uuid import UUID

from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
)
from apps.rentals.domain.entities import Apartment, House
from apps.rentals.domain.exceptions import ApartmentNotFound, HouseNotFound
from apps.rentals.domain.value_objects import ApartmentId, HouseId


def require_house_for_owner(
    houses: HouseRepository, house_id: HouseId, owner_id: UUID
) -> House:
    """Return the house only when it exists and belongs to ``owner_id``."""
    house = houses.get_by_id(house_id)
    if house is None or house.owner_id.value != owner_id:
        raise HouseNotFound("House not found.")
    return house


def require_apartment_for_owner(
    apartments: ApartmentRepository,
    houses: HouseRepository,
    apartment_id: ApartmentId,
    owner_id: UUID,
) -> Apartment:
    """Return the apartment only when its house belongs to ``owner_id``."""
    apartment = apartments.get_by_id(apartment_id)
    if apartment is None:
        raise ApartmentNotFound("Apartment not found.")
    house = houses.get_by_id(apartment.house_id)
    if house is None or house.owner_id.value != owner_id:
        raise ApartmentNotFound("Apartment not found.")
    return apartment
