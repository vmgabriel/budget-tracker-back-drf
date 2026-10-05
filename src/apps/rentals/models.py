"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.rentals.infrastructure.persistence.models import (
    ApartmentModel,
    DocumentModel,
    HouseModel,
    PaymentRecordModel,
    UtilityReadingModel,
)

__all__ = (
    "ApartmentModel",
    "DocumentModel",
    "HouseModel",
    "PaymentRecordModel",
    "UtilityReadingModel",
)
