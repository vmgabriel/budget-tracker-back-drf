"""Payment record listing use case."""

from datetime import date
from uuid import UUID

from apps.rentals.application.dto import PaymentRecordDetails, payment_record_details
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    PaymentRecordRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.value_objects import ApartmentId


class ListApartmentPayments:
    """Return payment records of an apartment filtered by date range."""

    def __init__(
        self,
        payments: PaymentRecordRepository,
        apartments: ApartmentRepository,
        houses: HouseRepository,
    ) -> None:
        self._payments = payments
        self._apartments = apartments
        self._houses = houses

    def execute(
        self,
        apartment_id: UUID,
        owner_id: UUID,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[PaymentRecordDetails]:
        require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        if start_date is not None and end_date is not None and start_date > end_date:
            raise InvalidRentalsInput("start_date must not be after end_date.")
        records = self._payments.get_by_apartment_id(ApartmentId(apartment_id))
        if start_date is not None:
            records = [r for r in records if r.payment_date >= start_date]
        if end_date is not None:
            records = [r for r in records if r.payment_date <= end_date]
        return [payment_record_details(record) for record in records]
