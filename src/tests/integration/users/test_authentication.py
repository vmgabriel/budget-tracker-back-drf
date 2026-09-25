"""JWT authentication endpoint integration tests."""

from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.mark.django_db
class TestJWTAuthentication:
    def test_obtain_token(self) -> None:
        user: Any = UserFactory(email="test@example.com", password="securepass123")
        client = APIClient()

        response = client.post(
            reverse("api_v1:users:login"),
            {"email": "TEST@example.com", "password": "securepass123"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user_id"] == str(user.id)
        assert response.data["email"] == "test@example.com"
        assert response.data["full_name"] == user.full_name
        assert "sessionid" not in response.cookies
        assert "csrftoken" not in response.cookies

    def test_refresh_token(self) -> None:
        UserFactory(email="test@example.com", password="securepass123")
        client = APIClient()
        login = client.post(
            reverse("api_v1:users:login"),
            {"email": "test@example.com", "password": "securepass123"},
            format="json",
        )

        response = client.post(
            reverse("api_v1:users:refresh"),
            {"refresh": login.data["refresh"]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_protected_endpoint_with_valid_token(self, jwt_token_factory: Any) -> None:
        user = UserFactory()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_token_factory(user)}")

        response = client.get(reverse("api_v1:users:current-user"))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_protected_endpoint_without_token(self) -> None:
        response = APIClient().get(reverse("api_v1:users:current-user"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response["WWW-Authenticate"].startswith("Bearer")

    def test_protected_endpoint_with_invalid_token(self) -> None:
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token")

        response = client.get(reverse("api_v1:users:current-user"))

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_deactivated_user_cannot_use_or_refresh_tokens(
        self, jwt_token_factory: Any
    ) -> None:
        user: Any = UserFactory()
        access_token = jwt_token_factory(user)
        refresh = RefreshToken.for_user(user)
        user.is_active = False
        user.save(update_fields=("is_active",))

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        protected = client.get(reverse("api_v1:users:current-user"))
        refreshed = APIClient().post(
            reverse("api_v1:users:refresh"),
            {"refresh": str(refresh)},
            format="json",
        )

        assert protected.status_code == status.HTTP_401_UNAUTHORIZED
        assert refreshed.status_code == status.HTTP_401_UNAUTHORIZED
