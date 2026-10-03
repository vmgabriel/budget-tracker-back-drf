"""Apartment creation use case."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import ApartmentDetails, apartment_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_house_for_owner
from apps.rentals.domain.entities import Apartment
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import (
    ApartmentNumber,
    HouseId,
    MonthlyRent,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CreateApartmentCommand:
    """Input required to create an apartment."""

    house_id: UUID
    owner_id: UUID
    number: str
    floor: int
    monthly_rent: Decimal


class CreateApartment:
    """Create and persist an apartment inside a user-owned house."""

    def __init__(
        self,
        apartments: ApartmentRepository,
        houses: HouseRepository,
        clock: Clock,
    ) -> None:
        self._apartments = apartments
        self._houses = houses
        self._clock = clock

    def execute(self, command: CreateApartmentCommand) -> ApartmentDetails:
        require_house_for_owner(
            self._houses, HouseId(command.house_id), command.owner_id
        )
        try:
            apartment = Apartment.create(
                house_id=HouseId(command.house_id),
                number=ApartmentNumber(command.number),
                floor=command.floor,
                monthly_rent=MonthlyRent(command.monthly_rent),
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return apartment_details(self._apartments.save(apartment))
