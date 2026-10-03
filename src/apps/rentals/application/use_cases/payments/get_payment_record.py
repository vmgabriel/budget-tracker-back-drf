"""Single payment record query use case."""

from uuid import UUID

from apps.rentals.application.dto import PaymentRecordDetails, payment_record_details
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    PaymentRecordRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.exceptions import ApartmentNotFound, PaymentRecordNotFound
from apps.rentals.domain.value_objects import PaymentRecordId


class GetPaymentRecord:
    """Return a payment only when its apartment belongs to the requesting user."""

    def __init__(
        self,
        payments: PaymentRecordRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._payments = payments
        self._apartments = apartments
        self._houses = houses

    def execute(self, payment_record_id: UUID, owner_id: UUID) -> PaymentRecordDetails:
        record = self._payments.get_by_id(PaymentRecordId(payment_record_id))
        if record is None:
            raise PaymentRecordNotFound("Payment record not found.")
        try:
            require_apartment_for_owner(
                self._apartments, self._houses, record.apartment_id, owner_id
            )
        except ApartmentNotFound as error:
            raise PaymentRecordNotFound("Payment record not found.") from error
        return payment_record_details(record)
