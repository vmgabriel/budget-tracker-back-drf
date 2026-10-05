"""Django admin discovery shim; registration lives in infrastructure."""

from apps.rentals.infrastructure.admin import (
    ApartmentAdmin,
    DocumentAdmin,
    HouseAdmin,
    PaymentRecordAdmin,
    UtilityReadingAdmin,
)

__all__ = (
    "ApartmentAdmin",
    "DocumentAdmin",
    "HouseAdmin",
    "PaymentRecordAdmin",
    "UtilityReadingAdmin",
)
