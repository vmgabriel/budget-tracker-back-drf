"""HTTP controllers for registration, JWT authentication, and user management."""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import (
    APIException,
    NotFound,
    ValidationError,
)
from rest_framework.exceptions import (
    AuthenticationFailed as DRFAuthenticationFailed,
)
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.api.serializers import PaginationQuerySerializer
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
from apps.users.interfaces.dependencies import build_user_use_cases
from apps.users.interfaces.serializers import (
    AdminUpdateUserSerializer,
    ChangeUserPlanSerializer,
    RegistrationSerializer,
    UserPageSerializer,
    UserSerializer,
)
from config.serializers import ERROR_RESPONSES


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


class TokenResponseSerializer(serializers.Serializer):
    """Document the token response returned after successful authentication."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    full_name = serializers.CharField(read_only=True)


class TokenRefreshResponseSerializer(serializers.Serializer):
    """Document access and rotated refresh tokens."""

    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True, required=False)


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Include safe user identity fields in a token pair response."""

    username_field = "email"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        # Preserve passwords containing meaningful leading/trailing spaces.
        self.fields["password"].trim_whitespace = False

    def validate(self, attrs: dict[str, object]) -> dict[str, str]:
        normalized_email = attrs.get("email")
        if isinstance(normalized_email, str):
            attrs["email"] = normalized_email.strip().lower()
        data = super().validate(attrs)
        if self.user is None:  # pragma: no cover - guarded by SimpleJWT validation
            raise DRFAuthenticationFailed("Invalid email or password.")
        data["user_id"] = str(self.user.id)
        data["email"] = self.user.email
        data["full_name"] = self.user.full_name
        return data


@extend_schema(auth=[])
class CustomTokenObtainPairView(TokenObtainPairView):
    """Issue access and refresh JWTs using email/password credentials."""

    serializer_class = CustomTokenObtainPairSerializer  # type: ignore[assignment]
    permission_classes = (AllowAny,)  # type: ignore[assignment]
    authentication_classes = ()

    @extend_schema(
        request=CustomTokenObtainPairSerializer,
        responses={status.HTTP_200_OK: TokenResponseSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().post(request, *args, **kwargs)


@extend_schema(
    auth=[],
    request=TokenRefreshSerializer,
    responses={status.HTTP_200_OK: TokenRefreshResponseSerializer, **ERROR_RESPONSES},
)
class CustomTokenRefreshView(TokenRefreshView):
    """Refresh an access token, rotating the refresh token when configured."""

    permission_classes = (AllowAny,)  # type: ignore[assignment]
    authentication_classes = ()


class LogoutResponseSerializer(serializers.Serializer):
    """Document the stateless logout acknowledgement."""

    message = serializers.CharField(read_only=True)


class LogoutView(APIView):
    """Acknowledge a stateless JWT logout.

    Access and refresh tokens are deliberately not stored or blacklisted. The
    client must discard both tokens after receiving this response.
    """

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        request=None,
        responses={
            status.HTTP_200_OK: LogoutResponseSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request) -> Response:
        del request
        return Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )


@extend_schema(auth=[])
class RegisterView(APIView):
    """Create a user account without requiring authentication."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    @extend_schema(
        request=RegistrationSerializer,
        responses={status.HTTP_201_CREATED: UserSerializer, **ERROR_RESPONSES},
    )
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


class CurrentUserView(APIView):
    """Return the user represented by the authenticated JWT."""

    permission_classes = (IsAuthenticated,)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(responses={status.HTTP_200_OK: UserSerializer, **ERROR_RESPONSES})
    def get(self, request: Request) -> Response:
        user_id = request.user.pk
        if not isinstance(user_id, UUID):
            raise ValidationError({"detail": "Authenticated identity is invalid."})
        try:
            user = build_user_use_cases().get.execute(UserId(user_id))
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)


class UserListView(APIView):
    """List users for staff administrators."""

    permission_classes = (IsAuthenticated, IsAdminUser)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="users_list",
        parameters=[PaginationQuerySerializer],
        responses={status.HTTP_200_OK: UserPageSerializer, **ERROR_RESPONSES},
    )
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


class UserDetailView(APIView):
    """Read or partially update a user as a staff administrator."""

    permission_classes = (IsAuthenticated, IsAdminUser)
    authentication_classes = (JWTAuthentication,)

    @staticmethod
    def _user_id(*, pk: UUID | None = None, user_id: UUID | None = None) -> UUID:
        selected_id = pk or user_id
        if selected_id is None:
            raise ValidationError({"detail": "A user identifier is required."})
        return selected_id

    @extend_schema(
        operation_id="users_retrieve",
        responses={status.HTTP_200_OK: UserSerializer, **ERROR_RESPONSES},
    )
    def get(
        self,
        request: Request,
        pk: UUID | None = None,
        user_id: UUID | None = None,
    ) -> Response:
        del request
        try:
            user = build_user_use_cases().get.execute(
                UserId(self._user_id(pk=pk, user_id=user_id))
            )
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)

    @extend_schema(
        request=AdminUpdateUserSerializer,
        responses={status.HTTP_200_OK: UserSerializer, **ERROR_RESPONSES},
    )
    def patch(
        self,
        request: Request,
        pk: UUID | None = None,
        user_id: UUID | None = None,
    ) -> Response:
        serializer = AdminUpdateUserSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            user = build_user_use_cases().admin_update.execute(
                AdminUpdateUserCommand(
                    user_id=UserId(self._user_id(pk=pk, user_id=user_id)),
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


class ChangeUserPlanView(APIView):
    """Change a user's subscription plan as a staff administrator."""

    permission_classes = (IsAuthenticated, IsAdminUser)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        request=ChangeUserPlanSerializer,
        responses={status.HTTP_200_OK: UserSerializer, **ERROR_RESPONSES},
    )
    def patch(
        self,
        request: Request,
        pk: UUID | None = None,
        user_id: UUID | None = None,
    ) -> Response:
        serializer = ChangeUserPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        selected_id = pk or user_id
        if selected_id is None:
            raise ValidationError({"detail": "A user identifier is required."})
        try:
            user = build_user_use_cases().change_plan.execute(
                ChangeUserPlanCommand(
                    user_id=UserId(selected_id),
                    plan=PlanLevel(str(serializer.validated_data["plan"])),
                )
            )
        except UserNotFound as exc:
            raise _translate_user_error(exc) from exc
        return _user_response(user)
