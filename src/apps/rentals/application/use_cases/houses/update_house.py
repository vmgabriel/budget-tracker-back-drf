"""House update use case."""

from dataclasses import dataclass
from uuid import UUID

from apps.rentals.application.dto import HouseDetails, house_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import HouseRepository
from apps.rentals.application.scope import require_house_for_owner
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import Address, HouseId
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdateHouseCommand:
    """Partial input accepted when updating a house.

    ``None`` leaves a field unchanged.
    """

    house_id: UUID
    owner_id: UUID
    name: str | None = None
    street: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None


class UpdateHouse:
    """Apply partial changes to a house owned by the requesting user."""

    def __init__(self, houses: HouseRepository, clock: Clock) -> None:
        self._houses = houses
        self._clock = clock

    def execute(self, command: UpdateHouseCommand) -> HouseDetails:
        if (
            command.name is None
            and command.street is None
            and command.city is None
            and command.state is None
            and command.country is None
        ):
            raise InvalidRentalsInput("At least one house field is required.")

        house = require_house_for_owner(
            self._houses, HouseId(command.house_id), command.owner_id
        )
        now = self._clock.now()
        try:
            if command.name is not None:
                house.rename(command.name, now=now)
            if (
                command.street is not None
                or command.city is not None
                or command.state is not None
                or command.country is not None
            ):
                address = Address(
                    street=(
                        command.street
                        if command.street is not None
                        else house.address.street
                    ),
                    city=(
                        command.city if command.city is not None else house.address.city
                    ),
                    state=(
                        command.state
                        if command.state is not None
                        else house.address.state
                    ),
                    country=(
                        command.country
                        if command.country is not None
                        else house.address.country
                    ),
                )
                house.change_address(address, now=now)
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return house_details(self._houses.update(house))
