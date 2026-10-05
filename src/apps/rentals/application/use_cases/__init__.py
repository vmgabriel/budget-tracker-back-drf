"""Rentals application use cases."""

from apps.rentals.application.use_cases.apartments import (
    CreateApartment,
    CreateApartmentCommand,
    DeleteApartment,
    GetApartment,
    ListHouseApartments,
    UpdateApartment,
    UpdateApartmentCommand,
)
from apps.rentals.application.use_cases.documents import (
    DeleteDocument,
    GetDocument,
    ListApartmentDocuments,
    UploadDocument,
    UploadDocumentCommand,
)
from apps.rentals.application.use_cases.houses import (
    CreateHouse,
    CreateHouseCommand,
    DeleteHouse,
    GetHouse,
    ListUserHouses,
    UpdateHouse,
    UpdateHouseCommand,
)
from apps.rentals.application.use_cases.payments import (
    GetPaymentRecord,
    GetPaymentSummary,
    ListApartmentPayments,
    RecordPayment,
    RecordPaymentCommand,
    UpdatePayment,
    UpdatePaymentCommand,
)
from apps.rentals.application.use_cases.utilities import (
    CalculateUtilityBill,
    GetUtilityReading,
    ListApartmentUtilityReadings,
    RecordUtilityReading,
    RecordUtilityReadingCommand,
)

__all__ = (
    "CalculateUtilityBill",
    "CreateApartment",
    "CreateApartmentCommand",
    "CreateHouse",
    "CreateHouseCommand",
    "DeleteApartment",
    "DeleteDocument",
    "DeleteHouse",
    "GetApartment",
    "GetDocument",
    "GetHouse",
    "GetPaymentRecord",
    "GetPaymentSummary",
    "GetUtilityReading",
    "ListApartmentDocuments",
    "ListApartmentPayments",
    "ListApartmentUtilityReadings",
    "ListHouseApartments",
    "ListUserHouses",
    "RecordPayment",
    "RecordPaymentCommand",
    "RecordUtilityReading",
    "RecordUtilityReadingCommand",
    "UpdateApartment",
    "UpdateApartmentCommand",
    "UpdateHouse",
    "UpdateHouseCommand",
    "UpdatePayment",
    "UpdatePaymentCommand",
    "UploadDocument",
    "UploadDocumentCommand",
)
