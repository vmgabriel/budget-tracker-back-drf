"""Payment record update use case."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import PaymentRecordDetails, payment_record_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    PaymentRecordRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    PaymentRecordNotFound,
    RentalsDomainError,
)
from apps.rentals.domain.value_objects import (
    PaymentAmount,
    PaymentRecordId,
    PaymentStatus,
)
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class UpdatePaymentCommand:
    """Partial input accepted when updating a payment record.

    ``None`` leaves a field unchanged. An empty ``notes`` string clears it.
    """

    payment_record_id: UUID
    owner_id: UUID
    amount: Decimal | None = None
    status: str | None = None
    notes: str | None = None


class UpdatePayment:
    """Apply partial changes to a payment record owned by the requesting user."""

    def __init__(
        self,
        payments: PaymentRecordRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
        clock: Clock,
    ) -> None:
        self._payments = payments
        self._apartments = apartments
        self._houses = houses
        self._clock = clock

    def execute(self, command: UpdatePaymentCommand) -> PaymentRecordDetails:
        if command.amount is None and command.status is None and command.notes is None:
            raise InvalidRentalsInput("At least one payment field is required.")

        record = self._payments.get_by_id(PaymentRecordId(command.payment_record_id))
        if record is None:
            raise PaymentRecordNotFound("Payment record not found.")
        try:
            apartment = require_apartment_for_owner(
                self._apartments, self._houses, record.apartment_id, command.owner_id
            )
        except ApartmentNotFound as error:
            raise PaymentRecordNotFound("Payment record not found.") from error

        try:
            record.update(
                amount=(
                    PaymentAmount(command.amount)
                    if command.amount is not None
                    else None
                ),
                status=(
                    PaymentStatus(command.status)
                    if command.status is not None
                    else None
                ),
                notes=command.notes,
                recalculate_status=(
                    command.amount is not None and command.status is None
                ),
                monthly_rent=apartment.monthly_rent,
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return payment_record_details(self._payments.update(record))
