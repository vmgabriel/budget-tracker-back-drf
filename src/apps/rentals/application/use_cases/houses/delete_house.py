"""House deletion use case."""

from uuid import UUID

from apps.rentals.application.ports.repositories import HouseRepository
from apps.rentals.application.scope import require_house_for_owner
from apps.rentals.domain.value_objects import HouseId


class DeleteHouse:
    """Delete a house only when it belongs to the requesting user."""

    def __init__(self, houses: HouseRepository) -> None:
        self._houses = houses

    def execute(self, house_id: UUID, owner_id: UUID) -> None:
        house = require_house_for_owner(self._houses, HouseId(house_id), owner_id)
        self._houses.delete(house)
