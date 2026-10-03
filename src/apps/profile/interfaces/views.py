"""HTTP controllers for the current user's profile and preferences."""

from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.profile.application.exceptions import InvalidProfileInput
from apps.profile.application.use_cases import (
    GetProfileCommand,
    UpdatePreferencesCommand,
    UpdateProfileCommand,
)
from apps.profile.domain.exceptions import ProfileNotFound
from apps.profile.domain.value_objects import UserId
from apps.profile.interfaces.dependencies import build_profile_use_cases
from apps.profile.interfaces.serializers import (
    ProfileSerializer,
    UpdatePreferencesSerializer,
    UpdateProfileSerializer,
)
from apps.users.interfaces.permissions import IsNotBanned
from config.serializers import ERROR_RESPONSES


def _authenticated_user_id(request: Request) -> UserId:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return UserId(user_id)


def _translate_profile_error(exc: Exception) -> APIException:
    if isinstance(exc, ProfileNotFound):
        return NotFound(str(exc))
    if isinstance(exc, InvalidProfileInput):
        return ValidationError({"detail": str(exc)})
    return ValidationError({"detail": "The request could not be processed."})


def _profile_response(profile: object) -> Response:
    return Response(ProfileSerializer(profile).data)


class CurrentProfileView(APIView):
    """Retrieve or update the authenticated user's own profile."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="profile_retrieve",
        responses={status.HTTP_200_OK: ProfileSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        try:
            profile = build_profile_use_cases().get.execute(
                GetProfileCommand(user_id=_authenticated_user_id(request))
            )
        except ProfileNotFound as error:
            raise _translate_profile_error(error) from error
        return _profile_response(profile)

    @extend_schema(
        operation_id="profile_partial_update",
        request=UpdateProfileSerializer,
        responses={status.HTTP_200_OK: ProfileSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request) -> Response:
        serializer = UpdateProfileSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            profile = build_profile_use_cases().update.execute(
                UpdateProfileCommand(
                    user_id=_authenticated_user_id(request),
                    first_name=(
                        str(data["first_name"]) if "first_name" in data else None
                    ),
                    last_name=(str(data["last_name"]) if "last_name" in data else None),
                    timezone=(str(data["timezone"]) if "timezone" in data else None),
                    avatar_url=(
                        str(data["avatar_url"]) if "avatar_url" in data else None
                    ),
                    bio=str(data["bio"]) if "bio" in data else None,
                )
            )
        except (InvalidProfileInput, ProfileNotFound) as error:
            raise _translate_profile_error(error) from error
        return _profile_response(profile)


class UpdatePreferencesView(APIView):
    """Update the authenticated user's regional preferences."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="profile_preferences_partial_update",
        request=UpdatePreferencesSerializer,
        responses={status.HTTP_200_OK: ProfileSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request) -> Response:
        serializer = UpdatePreferencesSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            profile = build_profile_use_cases().update_preferences.execute(
                UpdatePreferencesCommand(
                    user_id=_authenticated_user_id(request),
                    language=(str(data["language"]) if "language" in data else None),
                    currency=(str(data["currency"]) if "currency" in data else None),
                    date_format=(
                        str(data["date_format"]) if "date_format" in data else None
                    ),
                )
            )
        except (InvalidProfileInput, ProfileNotFound) as error:
            raise _translate_profile_error(error) from error
        return _profile_response(profile)
