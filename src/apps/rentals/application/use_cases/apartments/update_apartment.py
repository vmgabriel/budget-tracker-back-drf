"""Apartment update use case."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import ApartmentDetails, apartment_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import ApartmentId, ApartmentNumber, MonthlyRent
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdateApartmentCommand:
    """Partial input accepted when updating an apartment.

    ``None`` leaves a field unchanged.
    """

    apartment_id: UUID
    owner_id: UUID
    number: str | None = None
    floor: int | None = None
    monthly_rent: Decimal | None = None


class UpdateApartment:
    """Apply partial changes to an apartment owned by the requesting user."""

    def __init__(
        self,
        apartments: ApartmentRepository,
        houses: HouseRepository,
        clock: Clock,
    ) -> None:
        self._apartments = apartments
        self._houses = houses
        self._clock = clock

    def execute(self, command: UpdateApartmentCommand) -> ApartmentDetails:
        if (
            command.number is None
            and command.floor is None
            and command.monthly_rent is None
        ):
            raise InvalidRentalsInput("At least one apartment field is required.")

        apartment = require_apartment_for_owner(
            self._apartments,
            self._houses,
            ApartmentId(command.apartment_id),
            command.owner_id,
        )
        try:
            number = (
                ApartmentNumber(command.number)
                if command.number is not None
                else apartment.number
            )
            floor = command.floor if command.floor is not None else apartment.floor
            monthly_rent = (
                MonthlyRent(command.monthly_rent)
                if command.monthly_rent is not None
                else apartment.monthly_rent
            )
            apartment.update(
                number=number,
                floor=floor,
                monthly_rent=monthly_rent,
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return apartment_details(self._apartments.update(apartment))
