"""HTTP controllers for registration, authentication, and user management."""

from uuid import UUID

from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.application.exceptions import (
    AuthenticationFailed,
    InvalidUserInput,
)
from apps.users.application.use_cases import (
    AdminUpdateUserCommand,
    ChangeUserPlanCommand,
    CreateUserCommand,
)
from apps.users.domain.exceptions import EmailAlreadyExists, UserNotFound
from apps.users.domain.value_objects import PlanLevel, UserId
from apps.users.interfaces.dependencies import (
    build_authentication_use_cases,
    build_user_use_cases,
)
from apps.users.interfaces.serializers import (
    AdminUpdateUserSerializer,
    ChangeUserPlanSerializer,
    LoginSerializer,
    RegistrationSerializer,
    UserSerializer,
)


def _user_response(user: object) -> Response:
    return Response(UserSerializer(user).data)


def _translate_user_error(exc: Exception) -> APIException:
    if isinstance(exc, EmailAlreadyExists):
        return ValidationError({"email": [str(exc)]})
    if isinstance(exc, UserNotFound):
        return NotFound(str(exc))
    if isinstance(exc, InvalidUserInput):
        return ValidationError({"detail": str(exc)})
    if isinstance(exc, AuthenticationFailed):
        return ValidationError({"non_field_errors": [str(exc)]})
    return ValidationError({"detail": "The request could not be processed."})


class RegisterView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        use_cases = build_user_use_cases()
        try:
            user = use_cases.create.execute(
                CreateUserCommand(
                    email=str(data["email"]),
                    password=str(data["password"]),
                    full_name=str(data["full_name"]),
                )
            )
        except (EmailAlreadyExists, InvalidUserInput) as exc:
            raise _translate_user_error(exc) from exc
        response = _user_response(user)
        response.status_code = status.HTTP_201_CREATED
        return response


class LoginView(APIView):
    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        use_cases = build_authentication_use_cases(request._request)
        try:
            user = use_cases.authenticate.execute(
                email=str(data["email"]),
                password=str(data["password"]),
            )
        except (AuthenticationFailed, UserNotFound) as exc:
            raise _translate_user_error(exc) from exc
        get_token(request._request)
        return _user_response(user)


class LogoutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        build_authentication_use_cases(request._request).logout.execute()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        user_id = request.user.pk
        if not isinstance(user_id, UUID):
            raise ValidationError({"detail": "Authenticated identity is invalid."})
        try:
            user = build_user_use_cases().get.execute(UserId(user_id))
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)


class AdminUserListView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request: Request) -> Response:
        try:
            page = int(request.query_params.get("page", "1"))
            page_size = int(request.query_params.get("page_size", "20"))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"page": "Page and page_size must be integers."}
            ) from exc
        try:
            result = build_user_use_cases().list.execute(
                page=page,
                page_size=page_size,
            )
        except InvalidUserInput as exc:
            raise _translate_user_error(exc) from exc
        return Response(
            {
                "count": result.total,
                "page": page,
                "page_size": page_size,
                "results": [UserSerializer(user).data for user in result.items],
            }
        )


class AdminUserDetailView(APIView):
    permission_classes = (IsAdminUser,)

    def get(self, request: Request, user_id: UUID) -> Response:
        try:
            user = build_user_use_cases().get.execute(UserId(user_id))
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)

    def patch(self, request: Request, user_id: UUID) -> Response:
        serializer = AdminUpdateUserSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = build_user_use_cases().admin_update.execute(
                AdminUpdateUserCommand(
                    user_id=UserId(user_id),
                    email=str(data["email"]) if "email" in data else None,
                    full_name=(str(data["full_name"]) if "full_name" in data else None),
                    is_active=(
                        bool(data["is_active"]) if "is_active" in data else None
                    ),
                )
            )
        except (EmailAlreadyExists, UserNotFound, InvalidUserInput) as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)


class AdminUserPlanView(APIView):
    permission_classes = (IsAdminUser,)

    def patch(self, request: Request, user_id: UUID) -> Response:
        serializer = ChangeUserPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = build_user_use_cases().change_plan.execute(
                ChangeUserPlanCommand(
                    user_id=UserId(user_id),
                    plan=PlanLevel(str(serializer.validated_data["plan"])),
                )
            )
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)
