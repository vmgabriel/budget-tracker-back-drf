"""House creation use case."""

from dataclasses import dataclass
from uuid import UUID

from apps.rentals.application.dto import HouseDetails, house_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import HouseRepository
from apps.rentals.domain.entities import House
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import Address, UserId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class CreateHouseCommand:
    """Input required to create a house."""

    owner_id: UUID
    name: str
    street: str
    city: str
    state: str
    country: str


class CreateHouse:
    """Create and persist a house for an authenticated user."""

    def __init__(self, houses: HouseRepository, clock: Clock) -> None:
        self._houses = houses
        self._clock = clock

    def execute(self, command: CreateHouseCommand) -> HouseDetails:
        try:
            owner_id = UserId(command.owner_id)
            address = Address(
                street=command.street,
                city=command.city,
                state=command.state,
                country=command.country,
            )
            house = House.create(
                owner_id=owner_id,
                name=command.name,
                address=address,
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return house_details(self._houses.save(house))
