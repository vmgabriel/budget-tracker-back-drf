"""Rentals persistence ports."""

from apps.rentals.application.ports.repositories import (
    ApartmentRepository,
    DocumentRepository,
    HouseRepository,
    PaymentRecordRepository,
    UtilityReadingRepository,
)

__all__ = (
    "ApartmentRepository",
    "DocumentRepository",
    "HouseRepository",
    "PaymentRecordRepository",
    "UtilityReadingRepository",
)
