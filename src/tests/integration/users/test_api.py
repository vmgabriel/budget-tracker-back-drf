"""HTTP interface tests for JWT authentication and user management."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.domain.value_objects import PlanLevel
from tests.factories import UserFactory

User = get_user_model()
pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _bearer(client: APIClient, token: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_api_v1_routes_use_simplified_user_paths() -> None:
    assert reverse("api_v1:users:register") == "/api/v1/users/auth/register/"
    assert reverse("api_v1:users:user-list") == "/api/v1/users/"
    assert reverse("api_v1:users:login") == "/api/v1/users/auth/login/"
    assert reverse("api_v1:users:current-user") == "/api/v1/users/me/"


def test_authentication_endpoints_are_available() -> None:
    client = APIClient()
    credentials = {
        "email": "canonical@example.com",
        "full_name": "Canonical User",
        "password": "StrongPassword123!",
    }

    registered = client.post(
        reverse("api_v1:users:register"), credentials, format="json"
    )
    logged_in = client.post(
        reverse("api_v1:users:login"),
        {"email": credentials["email"], "password": credentials["password"]},
        format="json",
    )
    access_token = logged_in.data["access"]
    profile = _bearer(client, access_token).get(reverse("api_v1:users:current-user"))

    assert registered.status_code == status.HTTP_201_CREATED
    assert logged_in.status_code == status.HTTP_200_OK
    assert "access" in logged_in.data
    assert "refresh" in logged_in.data
    assert logged_in.data["email"] == credentials["email"]
    assert profile.status_code == status.HTTP_200_OK
    assert profile.data["email"] == credentials["email"]


def test_registration_login_me_and_logout() -> None:
    client = APIClient()
    credentials = {
        "email": "new-user@example.com",
        "full_name": "New User",
        "password": "StrongPassword123!",
    }

    registration = client.post(
        reverse("api_v1:users:register"), credentials, format="json"
    )

    assert registration.status_code == status.HTTP_201_CREATED
    created = User.objects.get(email="new-user@example.com")
    assert registration.data["id"] == str(created.id)
    assert registration.data["email"] == "new-user@example.com"
    assert registration.data["plan"] == PlanLevel.FREE.value
    assert created.check_password(credentials["password"])

    login = client.post(
        reverse("api_v1:users:login"),
        {"email": credentials["email"], "password": credentials["password"]},
        format="json",
    )
    assert login.status_code == status.HTTP_200_OK
    access_token = login.data["access"]

    me = _bearer(client, access_token).get(reverse("api_v1:users:current-user"))
    assert me.status_code == status.HTTP_200_OK
    assert me.data["email"] == "new-user@example.com"

    logout = client.post(reverse("api_v1:users:logout"))
    assert logout.status_code == status.HTTP_200_OK
    assert logout.data["message"] == "Successfully logged out"

    # Logout is stateless: it acknowledges the request but does not revoke JWTs.
    without_token = APIClient().get(reverse("api_v1:users:current-user"))
    assert without_token.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_returns_a_new_access_token() -> None:
    UserFactory(email="refresh@example.com", password="StrongPassword123!")
    client = APIClient()
    login = client.post(
        reverse("api_v1:users:login"),
        {"email": "refresh@example.com", "password": "StrongPassword123!"},
        format="json",
    )
    assert login.status_code == status.HTTP_200_OK

    refreshed = client.post(
        reverse("api_v1:users:refresh"),
        {"refresh": login.data["refresh"]},
        format="json",
    )

    assert refreshed.status_code == status.HTTP_200_OK
    assert "access" in refreshed.data


def test_protected_endpoint_rejects_missing_and_invalid_tokens() -> None:
    missing = APIClient().get(reverse("api_v1:users:current-user"))
    invalid_client = APIClient()
    invalid_client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")
    invalid = invalid_client.get(reverse("api_v1:users:current-user"))

    assert missing.status_code == status.HTTP_401_UNAUTHORIZED
    assert invalid.status_code == status.HTTP_401_UNAUTHORIZED


def test_invalid_login_credentials_return_authentication_error() -> None:
    UserFactory(email="known@example.com", password="KnownPassword123!")
    client = APIClient()

    unknown = client.post(
        reverse("api_v1:users:login"),
        {"email": "unknown@example.com", "password": "WrongPassword123!"},
        format="json",
    )
    wrong_password = client.post(
        reverse("api_v1:users:login"),
        {"email": "known@example.com", "password": "WrongPassword123!"},
        format="json",
    )

    assert unknown.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_password.status_code == status.HTTP_401_UNAUTHORIZED
    assert unknown.data["error"]["code"] == "authentication_failed"
    assert wrong_password.data["error"]["code"] == "authentication_failed"


def test_duplicate_registration_is_rejected() -> None:
    UserFactory(email="duplicate@example.com")
    client = APIClient()

    response = client.post(
        reverse("api_v1:users:register"),
        {
            "email": "DUPLICATE@example.com",
            "full_name": "Another User",
            "password": "StrongPassword123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_admin_list_rejects_oversized_page(
    jwt_token_factory: Any,
) -> None:
    administrator: Any = UserFactory(
        email="admin-page-limit@example.com", is_staff=True
    )
    client = _bearer(APIClient(), jwt_token_factory(administrator))

    response = client.get(reverse("api_v1:users:user-list"), {"page": 10_001})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_admin_can_list_and_change_plan_but_regular_user_cannot(
    jwt_token_factory: Any,
) -> None:
    target: Any = UserFactory(email="target@example.com")
    regular_user = UserFactory(email="regular@example.com")
    administrator = UserFactory(email="admin@example.com", is_staff=True)
    client = APIClient()

    _bearer(client, jwt_token_factory(regular_user))
    forbidden = client.get(reverse("api_v1:users:user-list"))
    assert forbidden.status_code == status.HTTP_403_FORBIDDEN

    _bearer(client, jwt_token_factory(administrator))
    listing = client.get(reverse("api_v1:users:user-list"))
    assert listing.status_code == status.HTTP_200_OK
    assert listing.data["count"] >= 3

    plan_response = client.patch(
        reverse("api_v1:users:change-plan", kwargs={"pk": target.id}),
        {"plan": PlanLevel.PREMIUM.value},
        format="json",
    )
    assert plan_response.status_code == status.HTTP_200_OK
    target.refresh_from_db()
    assert target.plan == PlanLevel.PREMIUM.value

    profile_response = client.patch(
        reverse("api_v1:users:user-detail", kwargs={"pk": target.id}),
        {
            "email": "updated-target@example.com",
            "full_name": "Updated Target",
            "is_active": False,
        },
        format="json",
    )
    assert profile_response.status_code == status.HTTP_200_OK
    target.refresh_from_db()
    assert target.email == "updated-target@example.com"
    assert target.full_name == "Updated Target"
    assert target.is_active is False
