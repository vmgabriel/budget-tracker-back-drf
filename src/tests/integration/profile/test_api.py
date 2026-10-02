"""Profile HTTP interface tests using JWT authentication."""

from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.profile.infrastructure.persistence.models import ProfileModel
from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _authenticated_client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def _profile_url() -> str:
    return reverse("api_v1:profile:current-profile")


def _preferences_url() -> str:
    return reverse("api_v1:profile:update-preferences")


def test_api_v1_routes_keep_minimal_profile_paths() -> None:
    assert _profile_url() == "/api/v1/profile/me/"
    assert _preferences_url() == "/api/v1/profile/me/preferences/"


def test_get_profile_returns_the_auto_provisioned_defaults(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory(full_name="Api Owner")
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(_profile_url())

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Api"
    assert response.data["last_name"] == "Owner"
    assert response.data["timezone"] == "UTC"
    assert response.data["language"] == "es"
    assert response.data["currency"] == "USD"
    assert response.data["date_format"] == "YYYY-MM-DD"
    assert response.data["avatar_url"] is None
    assert response.data["bio"] is None
    profile = ProfileModel.objects.get(user=owner)
    assert response.data["id"] == str(profile.pk)


def test_get_profile_is_scoped_to_the_authenticated_user(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory(full_name="First Owner")
    other: Any = UserFactory(full_name="Second Owner")
    client = _authenticated_client(other, jwt_token_factory)

    response = client.get(_profile_url())

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Second"
    assert response.data["id"] != str(ProfileModel.objects.get(user=owner).pk)


def test_patch_profile_updates_details_and_preserves_other_fields(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(
        _profile_url(),
        {
            "first_name": "Renamed",
            "timezone": "America/Bogota",
            "bio": "  Keeps a budget.  ",
            "avatar_url": "https://cdn.example.com/a.png",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["first_name"] == "Renamed"
    assert response.data["timezone"] == "America/Bogota"
    assert response.data["bio"] == "Keeps a budget."
    assert response.data["avatar_url"] == "https://cdn.example.com/a.png"
    assert response.data["language"] == "es"
    profile = ProfileModel.objects.get(user=owner)
    assert profile.timezone == "America/Bogota"
    assert profile.bio == "Keeps a budget."


def test_patch_profile_clears_optional_fields_with_blank_strings(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)
    client.patch(
        _profile_url(),
        {"bio": "Temporary", "avatar_url": "https://cdn.example.com/a.png"},
        format="json",
    )

    response = client.patch(
        _profile_url(), {"bio": "", "avatar_url": ""}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["bio"] is None
    assert response.data["avatar_url"] is None
    profile = ProfileModel.objects.get(user=owner)
    assert profile.bio is None
    assert profile.avatar_url is None


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"timezone": "Fake/Zone"}, "timezone"),
        ({"avatar_url": "not-a-url"}, "avatar_url"),
        ({"bio": "x" * 501}, "bio"),
        ({"first_name": ""}, "first_name"),
        ({"first_name": " ", "last_name": " "}, "detail"),
    ],
)
def test_patch_profile_rejects_invalid_input_with_field_errors(
    payload: dict[str, str],
    field: str,
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(_profile_url(), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data
    profile = ProfileModel.objects.get(user=owner)
    assert profile.timezone == "UTC"


def test_patch_profile_rejects_an_empty_payload(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(_profile_url(), {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_patch_preferences_updates_and_normalizes_values(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(
        _preferences_url(),
        {"language": "PT", "currency": "cop", "date_format": "DD/MM/YYYY"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["language"] == "pt"
    assert response.data["currency"] == "COP"
    assert response.data["date_format"] == "DD/MM/YYYY"
    assert response.data["first_name"] == "Test"
    profile = ProfileModel.objects.get(user=owner)
    assert profile.language == "pt"
    assert profile.currency == "COP"
    assert profile.date_format == "DD/MM/YYYY"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"language": "xx"}, "language"),
        ({"currency": "XYZ"}, "currency"),
        ({"date_format": "31-12-2026"}, "date_format"),
    ],
)
def test_patch_preferences_rejects_invalid_input_with_field_errors(
    payload: dict[str, str],
    field: str,
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(_preferences_url(), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.data
    profile = ProfileModel.objects.get(user=owner)
    assert profile.language == "es"


def test_patch_preferences_rejects_an_empty_payload(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.patch(_preferences_url(), {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_profile_endpoints_require_jwt_authentication() -> None:
    client = APIClient()

    assert client.get(_profile_url()).status_code == status.HTTP_401_UNAUTHORIZED
    assert (
        client.patch(_profile_url(), {"first_name": "Ana"}, format="json").status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.patch(_preferences_url(), {"language": "en"}, format="json").status_code
        == status.HTTP_401_UNAUTHORIZED
    )
