"""Composition root for the rentals bounded context."""

from dataclasses import dataclass

from apps.rentals.application.use_cases import (
    CalculateUtilityBill,
    CreateApartment,
    CreateHouse,
    DeleteApartment,
    DeleteDocument,
    DeleteHouse,
    GetApartment,
    GetDocument,
    GetHouse,
    GetPaymentRecord,
    GetPaymentSummary,
    GetUtilityReading,
    ListApartmentDocuments,
    ListApartmentPayments,
    ListApartmentUtilityReadings,
    ListHouseApartments,
    ListUserHouses,
    RecordPayment,
    RecordUtilityReading,
    UpdateApartment,
    UpdateHouse,
    UpdatePayment,
    UploadDocument,
)
from apps.rentals.infrastructure.persistence.repositories import (
    DjangoApartmentRepository,
    DjangoDocumentRepository,
    DjangoHouseRepository,
    DjangoPaymentRecordRepository,
    DjangoUtilityReadingRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class RentalsUseCases:
    """Rentals use cases sharing one set of persistence adapters."""

    create_house: CreateHouse
    get_house: GetHouse
    list_user_houses: ListUserHouses
    update_house: UpdateHouse
    delete_house: DeleteHouse
    create_apartment: CreateApartment
    get_apartment: GetApartment
    list_house_apartments: ListHouseApartments
    update_apartment: UpdateApartment
    delete_apartment: DeleteApartment
    upload_document: UploadDocument
    get_document: GetDocument
    list_apartment_documents: ListApartmentDocuments
    delete_document: DeleteDocument
    record_utility_reading: RecordUtilityReading
    get_utility_reading: GetUtilityReading
    list_apartment_utility_readings: ListApartmentUtilityReadings
    calculate_utility_bill: CalculateUtilityBill
    record_payment: RecordPayment
    get_payment_record: GetPaymentRecord
    list_apartment_payments: ListApartmentPayments
    get_payment_summary: GetPaymentSummary
    update_payment: UpdatePayment


def build_rentals_use_cases() -> RentalsUseCases:
    """Build rentals use cases with infrastructure dependencies."""
    houses = DjangoHouseRepository()
    apartments = DjangoApartmentRepository()
    documents = DjangoDocumentRepository()
    readings = DjangoUtilityReadingRepository()
    payments = DjangoPaymentRecordRepository()
    clock = SystemClock()
    return RentalsUseCases(
        create_house=CreateHouse(houses, clock),
        get_house=GetHouse(houses),
        list_user_houses=ListUserHouses(houses),
        update_house=UpdateHouse(houses, clock),
        delete_house=DeleteHouse(houses),
        create_apartment=CreateApartment(apartments, houses, clock),
        get_apartment=GetApartment(apartments, houses),
        list_house_apartments=ListHouseApartments(apartments, houses),
        update_apartment=UpdateApartment(apartments, houses, clock),
        delete_apartment=DeleteApartment(apartments, houses),
        upload_document=UploadDocument(documents, apartments, houses, clock),
        get_document=GetDocument(documents, apartments, houses),
        list_apartment_documents=ListApartmentDocuments(documents, apartments, houses),
        delete_document=DeleteDocument(documents, apartments, houses),
        record_utility_reading=RecordUtilityReading(
            readings, apartments, houses, clock
        ),
        get_utility_reading=GetUtilityReading(readings, apartments, houses),
        list_apartment_utility_readings=ListApartmentUtilityReadings(
            readings, apartments, houses
        ),
        calculate_utility_bill=CalculateUtilityBill(readings, apartments, houses),
        record_payment=RecordPayment(payments, apartments, houses, clock),
        get_payment_record=GetPaymentRecord(payments, apartments, houses),
        list_apartment_payments=ListApartmentPayments(payments, apartments, houses),
        get_payment_summary=GetPaymentSummary(payments, apartments, houses),
        update_payment=UpdatePayment(payments, apartments, houses, clock),
    )
