"""House listing use case."""

from uuid import UUID

from apps.rentals.application.dto import HouseDetails, house_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import HouseRepository
from apps.rentals.domain.value_objects import UserId


class ListUserHouses:
    """Return every house owned by the requesting user."""

    def __init__(self, houses: HouseRepository) -> None:
        self._houses = houses

    def execute(self, owner_id: UUID) -> list[HouseDetails]:
        try:
            houses = self._houses.get_by_owner_id(UserId(owner_id))
        except TypeError as error:
            raise InvalidRentalsInput(str(error)) from error
        return [house_details(house) for house in houses]
