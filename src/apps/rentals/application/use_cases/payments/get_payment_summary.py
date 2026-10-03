"""Payment summary use case."""

from decimal import Decimal
from uuid import UUID

from apps.rentals.application.dto import PaymentSummaryDetails, Period
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    HouseRepository,
    PaymentRecordRepository,
)
from apps.rentals.application.scope import require_apartment_for_owner
from apps.rentals.domain.entities import Apartment
from apps.rentals.domain.value_objects import ApartmentId


class GetPaymentSummary:
    """Aggregate paid amounts and outstanding balance for one month."""

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
        self, apartment_id: UUID, owner_id: UUID, period: Period
    ) -> PaymentSummaryDetails:
        apartment: Apartment = require_apartment_for_owner(
            self._apartments, self._houses, ApartmentId(apartment_id), owner_id
        )
        if not isinstance(period, Period):
            raise InvalidRentalsInput("Period must be a Period.")
        records = self._payments.get_by_apartment_and_period(
            ApartmentId(apartment_id), period
        )
        total_paid = sum((record.amount.amount for record in records), Decimal("0"))
        outstanding = max(apartment.monthly_rent.amount - total_paid, Decimal("0"))
        return PaymentSummaryDetails(
            apartment_id=ApartmentId(apartment_id),
            year=period.year,
            month=period.month,
            total_paid=total_paid.quantize(Decimal("0.01")),
            outstanding_balance=outstanding.quantize(Decimal("0.01")),
            payment_count=len(records),
        )
