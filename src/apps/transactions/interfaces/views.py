"""HTTP controllers for owner-scoped transaction CRUD operations."""

from uuid import UUID

from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.transactions.application.exceptions import InvalidTransactionInput
from apps.transactions.application.use_cases import (
    CreateTransactionCommand,
    UpdateTransactionCommand,
)
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import TransactionId, TransactionType
from apps.transactions.interfaces.dependencies import build_transaction_use_cases
from apps.transactions.interfaces.serializers import (
    CreateTransactionSerializer,
    TransactionSerializer,
    UpdateTransactionSerializer,
)


def _authenticated_user_id(request: Request) -> UUID:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return user_id


def _translate_transaction_error(exc: Exception) -> APIException:
    if isinstance(exc, TransactionNotFound):
        return NotFound(str(exc))
    if isinstance(exc, InvalidTransactionInput):
        return ValidationError({"detail": str(exc)})
    return ValidationError({"detail": "The request could not be processed."})


def _transaction_response(transaction: object) -> Response:
    return Response(TransactionSerializer(transaction).data)


class TransactionListCreateView(APIView):
    """List the authenticated user's transactions or create one."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "20"))
        except (TypeError, ValueError) as error:
            raise ValidationError(
                {"page": "Page and page_size must be integers."}
            ) from error
        try:
            result = build_transaction_use_cases().list.execute(
                _authenticated_user_id(request),
                page=page,
                page_size=page_size,
            )
        except InvalidTransactionInput as error:
            raise _translate_transaction_error(error) from error
        return Response(
            {
                "count": result.total,
                "page": page,
                "page_size": page_size,
                "results": [
                    TransactionSerializer(transaction).data
                    for transaction in result.items
                ],
            }
        )

    def post(self, request: Request) -> Response:
        serializer = CreateTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            transaction = build_transaction_use_cases().create.execute(
                CreateTransactionCommand(
                    user_id=_authenticated_user_id(request),
                    amount=data["amount"],
                    transaction_type=TransactionType(str(data["transaction_type"])),
                    category=str(data["category"]),
                    date=data["date"],
                    description=(
                        str(data["description"]) if "description" in data else None
                    ),
                )
            )
        except InvalidTransactionInput as error:
            raise _translate_transaction_error(error) from error
        response = _transaction_response(transaction)
        response.status_code = status.HTTP_201_CREATED
        return response


class TransactionDetailView(APIView):
    """Retrieve, update, or delete one transaction owned by the current user."""

    permission_classes = (IsAuthenticated,)

    def get(self, request: Request, transaction_id: UUID) -> Response:
        try:
            transaction = build_transaction_use_cases().get.execute(
                TransactionId(transaction_id),
                _authenticated_user_id(request),
            )
        except TransactionNotFound as error:
            raise _translate_transaction_error(error) from error
        return _transaction_response(transaction)

    def patch(self, request: Request, transaction_id: UUID) -> Response:
        serializer = UpdateTransactionSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            transaction = build_transaction_use_cases().update.execute(
                UpdateTransactionCommand(
                    transaction_id=TransactionId(transaction_id),
                    user_id=_authenticated_user_id(request),
                    amount=data.get("amount"),
                    transaction_type=(
                        TransactionType(str(data["transaction_type"]))
                        if "transaction_type" in data
                        else None
                    ),
                    category=(str(data["category"]) if "category" in data else None),
                    date=data.get("date"),
                    description=(
                        str(data["description"]) if "description" in data else None
                    ),
                )
            )
        except (InvalidTransactionInput, TransactionNotFound) as error:
            raise _translate_transaction_error(error) from error
        return _transaction_response(transaction)

    def delete(self, request: Request, transaction_id: UUID) -> Response:
        try:
            build_transaction_use_cases().delete.execute(
                TransactionId(transaction_id),
                _authenticated_user_id(request),
            )
        except TransactionNotFound as error:
            raise _translate_transaction_error(error) from error
        return Response(status=status.HTTP_204_NO_CONTENT)
