"""HTTP controllers for the rentals bounded context."""

from datetime import date
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.rentals.application.dto import Period
from apps.rentals.application.exceptions import InvalidRentalsInput
from apps.rentals.application.use_cases import (
    CreateApartmentCommand,
    CreateHouseCommand,
    RecordPaymentCommand,
    RecordUtilityReadingCommand,
    UpdateApartmentCommand,
    UpdateHouseCommand,
    UpdatePaymentCommand,
    UploadDocumentCommand,
)
from apps.rentals.domain.exceptions import (
    ApartmentNotFound,
    DocumentNotFound,
    HouseNotFound,
    InvalidAddress,
    InvalidPaymentAmount,
    InvalidReading,
    PaymentRecordNotFound,
    UtilityReadingNotFound,
)
from apps.rentals.interfaces.dependencies import build_rentals_use_cases
from apps.rentals.interfaces.serializers import (
    ApartmentDetailsSerializer,
    CreateApartmentSerializer,
    CreateHouseSerializer,
    DocumentDetailsSerializer,
    HouseDetailsSerializer,
    PaymentRecordDetailsSerializer,
    PaymentSummaryDetailsSerializer,
    RecordPaymentSerializer,
    RecordUtilityReadingSerializer,
    UpdateApartmentSerializer,
    UpdateHouseSerializer,
    UpdatePaymentSerializer,
    UploadDocumentSerializer,
    UtilityBillDetailsSerializer,
    UtilityReadingDetailsSerializer,
)
from apps.users.interfaces.permissions import IsNotBanned
from config.serializers import ERROR_RESPONSES

NOT_FOUND_ERRORS = (
    HouseNotFound,
    ApartmentNotFound,
    DocumentNotFound,
    PaymentRecordNotFound,
    UtilityReadingNotFound,
)


def _authenticated_user_id(request: Request) -> UUID:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return user_id


def _translate_rentals_error(exc: Exception) -> APIException:
    if isinstance(exc, NOT_FOUND_ERRORS):
        return NotFound(str(exc))
    if isinstance(
        exc, (InvalidRentalsInput, InvalidReading, InvalidPaymentAmount, InvalidAddress)
    ):
        return ValidationError({"detail": str(exc)})
    return ValidationError({"detail": "The request could not be processed."})


def _parse_period(request: Request) -> Period:
    try:
        year = int(str(request.query_params["year"]))
        month = int(str(request.query_params["month"]))
    except (KeyError, TypeError, ValueError) as error:
        raise ValidationError(
            {"detail": "Both 'year' and 'month' query parameters are required."}
        ) from error
    try:
        return Period(year=year, month=month)
    except (TypeError, ValueError) as error:
        raise ValidationError({"detail": str(error)}) from error


def _parse_optional_date(request: Request, name: str) -> date | None:
    raw = request.query_params.get(name)
    if raw is None:
        return None
    try:
        return date.fromisoformat(raw)
    except (TypeError, ValueError) as error:
        raise ValidationError({name: "Use ISO format YYYY-MM-DD."}) from error


class HouseListView(APIView):
    """List the authenticated user's houses or create one."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_houses_list",
        responses={
            status.HTTP_200_OK: HouseDetailsSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request) -> Response:
        houses = build_rentals_use_cases().list_user_houses.execute(
            _authenticated_user_id(request)
        )
        return Response(HouseDetailsSerializer(houses, many=True).data)

    @extend_schema(
        operation_id="rentals_houses_create",
        request=CreateHouseSerializer,
        responses={status.HTTP_201_CREATED: HouseDetailsSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        serializer = CreateHouseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            house = build_rentals_use_cases().create_house.execute(
                CreateHouseCommand(
                    owner_id=_authenticated_user_id(request),
                    name=serializer.validated_data["name"],
                    street=serializer.validated_data["street"],
                    city=serializer.validated_data["city"],
                    state=serializer.validated_data["state"],
                    country=serializer.validated_data["country"],
                )
            )
        except InvalidRentalsInput as error:
            raise _translate_rentals_error(error) from error
        response = Response(HouseDetailsSerializer(house).data)
        response.status_code = status.HTTP_201_CREATED
        return response


class HouseDetailView(APIView):
    """Retrieve, update, or delete one house owned by the current user."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_houses_retrieve",
        responses={status.HTTP_200_OK: HouseDetailsSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request, pk: UUID) -> Response:
        try:
            house = build_rentals_use_cases().get_house.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(HouseDetailsSerializer(house).data)

    @extend_schema(
        operation_id="rentals_houses_partial_update",
        request=UpdateHouseSerializer,
        responses={status.HTTP_200_OK: HouseDetailsSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request, pk: UUID) -> Response:
        serializer = UpdateHouseSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            house = build_rentals_use_cases().update_house.execute(
                UpdateHouseCommand(
                    house_id=pk,
                    owner_id=_authenticated_user_id(request),
                    name=serializer.validated_data.get("name"),
                    street=serializer.validated_data.get("street"),
                    city=serializer.validated_data.get("city"),
                    state=serializer.validated_data.get("state"),
                    country=serializer.validated_data.get("country"),
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(HouseDetailsSerializer(house).data)

    @extend_schema(
        operation_id="rentals_houses_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, pk: UUID) -> Response:
        try:
            build_rentals_use_cases().delete_house.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(status=status.HTTP_204_NO_CONTENT)


class ApartmentListView(APIView):
    """List apartments of a house, optionally filtered, or create one."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_apartments_list",
        responses={
            status.HTTP_200_OK: ApartmentDetailsSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request) -> Response:
        raw_house_id = request.query_params.get("house_id")
        if raw_house_id is None:
            raise ValidationError({"house_id": "This query parameter is required."})
        try:
            house_id = UUID(str(raw_house_id))
        except ValueError as error:
            raise ValidationError({"house_id": "Must be a valid UUID."}) from error
        try:
            apartments = build_rentals_use_cases().list_house_apartments.execute(
                house_id, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(ApartmentDetailsSerializer(apartments, many=True).data)

    @extend_schema(
        operation_id="rentals_apartments_create",
        request=CreateApartmentSerializer,
        responses={
            status.HTTP_201_CREATED: ApartmentDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CreateApartmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            apartment = build_rentals_use_cases().create_apartment.execute(
                CreateApartmentCommand(
                    house_id=serializer.validated_data["house_id"],
                    owner_id=_authenticated_user_id(request),
                    number=serializer.validated_data["number"],
                    floor=serializer.validated_data["floor"],
                    monthly_rent=serializer.validated_data["monthly_rent"],
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        response = Response(ApartmentDetailsSerializer(apartment).data)
        response.status_code = status.HTTP_201_CREATED
        return response


class ApartmentDetailView(APIView):
    """Retrieve, update, or delete one apartment owned by the current user."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_apartments_retrieve",
        responses={status.HTTP_200_OK: ApartmentDetailsSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request, pk: UUID) -> Response:
        try:
            apartment = build_rentals_use_cases().get_apartment.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(ApartmentDetailsSerializer(apartment).data)

    @extend_schema(
        operation_id="rentals_apartments_partial_update",
        request=UpdateApartmentSerializer,
        responses={status.HTTP_200_OK: ApartmentDetailsSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request, pk: UUID) -> Response:
        serializer = UpdateApartmentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            apartment = build_rentals_use_cases().update_apartment.execute(
                UpdateApartmentCommand(
                    apartment_id=pk,
                    owner_id=_authenticated_user_id(request),
                    number=serializer.validated_data.get("number"),
                    floor=serializer.validated_data.get("floor"),
                    monthly_rent=serializer.validated_data.get("monthly_rent"),
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(ApartmentDetailsSerializer(apartment).data)

    @extend_schema(
        operation_id="rentals_apartments_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, pk: UUID) -> Response:
        try:
            build_rentals_use_cases().delete_apartment.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(status=status.HTTP_204_NO_CONTENT)


class DocumentListView(APIView):
    """List or upload documents for one apartment."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_documents_list",
        responses={
            status.HTTP_200_OK: DocumentDetailsSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, apartment_id: UUID) -> Response:
        try:
            documents = build_rentals_use_cases().list_apartment_documents.execute(
                apartment_id, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(DocumentDetailsSerializer(documents, many=True).data)

    @extend_schema(
        operation_id="rentals_documents_create",
        request=UploadDocumentSerializer,
        responses={
            status.HTTP_201_CREATED: DocumentDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request, apartment_id: UUID) -> Response:
        serializer = UploadDocumentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            document = build_rentals_use_cases().upload_document.execute(
                UploadDocumentCommand(
                    apartment_id=apartment_id,
                    owner_id=_authenticated_user_id(request),
                    document_type=str(serializer.validated_data["document_type"]),
                    file_url=serializer.validated_data["file_url"],
                    description=serializer.validated_data.get("description") or None,
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        response = Response(DocumentDetailsSerializer(document).data)
        response.status_code = status.HTTP_201_CREATED
        return response


class DocumentDetailView(APIView):
    """Retrieve or delete one document owned by the current user."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_documents_retrieve",
        responses={status.HTTP_200_OK: DocumentDetailsSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request, pk: UUID) -> Response:
        try:
            document = build_rentals_use_cases().get_document.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(DocumentDetailsSerializer(document).data)

    @extend_schema(
        operation_id="rentals_documents_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, pk: UUID) -> Response:
        try:
            build_rentals_use_cases().delete_document.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(status=status.HTTP_204_NO_CONTENT)


class UtilityReadingListView(APIView):
    """List or record utility readings for one apartment."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_utility_readings_list",
        responses={
            status.HTTP_200_OK: UtilityReadingDetailsSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, apartment_id: UUID) -> Response:
        try:
            readings = (
                build_rentals_use_cases().list_apartment_utility_readings.execute(
                    apartment_id,
                    _authenticated_user_id(request),
                    utility_type=request.query_params.get("utility_type"),
                    start_date=_parse_optional_date(request, "start_date"),
                    end_date=_parse_optional_date(request, "end_date"),
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(UtilityReadingDetailsSerializer(readings, many=True).data)

    @extend_schema(
        operation_id="rentals_utility_readings_create",
        request=RecordUtilityReadingSerializer,
        responses={
            status.HTTP_201_CREATED: UtilityReadingDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request, apartment_id: UUID) -> Response:
        serializer = RecordUtilityReadingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            reading = build_rentals_use_cases().record_utility_reading.execute(
                RecordUtilityReadingCommand(
                    apartment_id=apartment_id,
                    owner_id=_authenticated_user_id(request),
                    utility_type=str(serializer.validated_data["utility_type"]),
                    reading_date=serializer.validated_data["reading_date"],
                    current_reading=serializer.validated_data["current_reading"],
                    previous_reading=serializer.validated_data["previous_reading"],
                    unit_cost=serializer.validated_data["unit_cost"],
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        response = Response(UtilityReadingDetailsSerializer(reading).data)
        response.status_code = status.HTTP_201_CREATED
        return response


class UtilityReadingDetailView(APIView):
    """Retrieve one utility reading."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_utility_readings_retrieve",
        responses={
            status.HTTP_200_OK: UtilityReadingDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, pk: UUID) -> Response:
        try:
            reading = build_rentals_use_cases().get_utility_reading.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(UtilityReadingDetailsSerializer(reading).data)


class UtilityBillView(APIView):
    """Aggregate one apartment's utility bill for a calendar month."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_utility_bill",
        responses={status.HTTP_200_OK: UtilityBillDetailsSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request, apartment_id: UUID) -> Response:
        utility_type = request.query_params.get("utility_type")
        if utility_type is None:
            raise ValidationError({"utility_type": "This query parameter is required."})
        try:
            bill = build_rentals_use_cases().calculate_utility_bill.execute(
                apartment_id,
                _authenticated_user_id(request),
                utility_type,
                _parse_period(request),
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(UtilityBillDetailsSerializer(bill).data)


class PaymentRecordListView(APIView):
    """List or record payments for one apartment."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_payments_list",
        responses={
            status.HTTP_200_OK: PaymentRecordDetailsSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, apartment_id: UUID) -> Response:
        try:
            records = build_rentals_use_cases().list_apartment_payments.execute(
                apartment_id,
                _authenticated_user_id(request),
                start_date=_parse_optional_date(request, "start_date"),
                end_date=_parse_optional_date(request, "end_date"),
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(PaymentRecordDetailsSerializer(records, many=True).data)

    @extend_schema(
        operation_id="rentals_payments_create",
        request=RecordPaymentSerializer,
        responses={
            status.HTTP_201_CREATED: PaymentRecordDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request, apartment_id: UUID) -> Response:
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = build_rentals_use_cases().record_payment.execute(
                RecordPaymentCommand(
                    apartment_id=apartment_id,
                    owner_id=_authenticated_user_id(request),
                    payment_date=serializer.validated_data["payment_date"],
                    amount=serializer.validated_data["amount"],
                    notes=serializer.validated_data.get("notes") or None,
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        response = Response(PaymentRecordDetailsSerializer(record).data)
        response.status_code = status.HTTP_201_CREATED
        return response


class PaymentRecordDetailView(APIView):
    """Retrieve or update one payment record."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_payments_retrieve",
        responses={
            status.HTTP_200_OK: PaymentRecordDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, pk: UUID) -> Response:
        try:
            record = build_rentals_use_cases().get_payment_record.execute(
                pk, _authenticated_user_id(request)
            )
        except NOT_FOUND_ERRORS as error:
            raise _translate_rentals_error(error) from error
        return Response(PaymentRecordDetailsSerializer(record).data)

    @extend_schema(
        operation_id="rentals_payments_partial_update",
        request=UpdatePaymentSerializer,
        responses={
            status.HTTP_200_OK: PaymentRecordDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def patch(self, request: Request, pk: UUID) -> Response:
        serializer = UpdatePaymentSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            record = build_rentals_use_cases().update_payment.execute(
                UpdatePaymentCommand(
                    payment_record_id=pk,
                    owner_id=_authenticated_user_id(request),
                    amount=serializer.validated_data.get("amount"),
                    status=(
                        str(serializer.validated_data["status"])
                        if "status" in serializer.validated_data
                        else None
                    ),
                    notes=serializer.validated_data.get("notes"),
                )
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(PaymentRecordDetailsSerializer(record).data)


class PaymentSummaryView(APIView):
    """Aggregate one apartment's payments for a calendar month."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="rentals_payment_summary",
        responses={
            status.HTTP_200_OK: PaymentSummaryDetailsSerializer,
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request, apartment_id: UUID) -> Response:
        try:
            summary = build_rentals_use_cases().get_payment_summary.execute(
                apartment_id,
                _authenticated_user_id(request),
                _parse_period(request),
            )
        except (InvalidRentalsInput, *NOT_FOUND_ERRORS) as error:
            raise _translate_rentals_error(error) from error
        return Response(PaymentSummaryDetailsSerializer(summary).data)
