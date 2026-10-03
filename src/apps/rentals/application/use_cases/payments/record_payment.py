"""Payment recording use case."""

from dataclasses import dataclass
from datetime import date
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
from apps.rentals.domain.entities import PaymentRecord
from apps.rentals.domain.exceptions import RentalsDomainError
from apps.rentals.domain.value_objects import ApartmentId, PaymentAmount
from shared.domain.ports.clock import Clock


@dataclass(frozen=True, slots=True)
class RecordPaymentCommand:
    """Input required to record a rent payment."""

    apartment_id: UUID
    owner_id: UUID
    payment_date: date
    amount: Decimal
    notes: str | None = None


class RecordPayment:
    """Record a payment, auto-calculating its status from the apartment rent."""

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

    def execute(self, command: RecordPaymentCommand) -> PaymentRecordDetails:
        apartment = require_apartment_for_owner(
            self._apartments,
            self._houses,
            ApartmentId(command.apartment_id),
            command.owner_id,
        )
        try:
            record = PaymentRecord.create(
                apartment_id=ApartmentId(command.apartment_id),
                payment_date=command.payment_date,
                amount=PaymentAmount(command.amount),
                monthly_rent=apartment.monthly_rent,
                notes=command.notes,
                now=self._clock.now(),
            )
        except (RentalsDomainError, TypeError, ValueError) as error:
            raise InvalidRentalsInput(str(error)) from error
        return payment_record_details(self._payments.save(record))
