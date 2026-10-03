"""HTTP interface tests for the admin ban workflow."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import UserFactory

User = get_user_model()
pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _bearer(client: APIClient, token: str) -> APIClient:
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def test_admin_can_ban_user_and_reason_is_stored(
    jwt_token_factory: Any,
) -> None:
    target: Any = UserFactory(email="ban-target@example.com")
    administrator: Any = UserFactory(email="ban-admin@example.com", is_staff=True)
    client = _bearer(APIClient(), jwt_token_factory(administrator))

    response = client.patch(
        reverse("api_v1:users:ban-user", kwargs={"pk": target.id}),
        {"reason": "Repeated terms-of-service violations"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    target.refresh_from_db()
    assert target.is_banned is True
    assert target.ban_reason == "Repeated terms-of-service violations"


def test_ban_requires_admin(jwt_token_factory: Any) -> None:
    target: Any = UserFactory(email="ban-guard-target@example.com")
    regular: Any = UserFactory(email="ban-regular@example.com")
    client = _bearer(APIClient(), jwt_token_factory(regular))

    response = client.patch(
        reverse("api_v1:users:ban-user", kwargs={"pk": target.id}),
        {"reason": "nope"},
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    target.refresh_from_db()
    assert target.is_banned is False


def test_banned_user_with_valid_jwt_gets_account_banned(
    jwt_token_factory: Any,
) -> None:
    administrator: Any = UserFactory(email="ban-admin2@example.com", is_staff=True)
    target: Any = UserFactory(email="banned-user@example.com")
    admin_client = _bearer(APIClient(), jwt_token_factory(administrator))
    ban = admin_client.patch(
        reverse("api_v1:users:ban-user", kwargs={"pk": target.id}),
        {"reason": "Fraudulent activity detected"},
        format="json",
    )
    assert ban.status_code == status.HTTP_200_OK

    target_client = _bearer(APIClient(), jwt_token_factory(target))
    response = target_client.get(reverse("api_v1:transactions:list"))

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.data["error"]["code"] == "account_banned"
    assert response.data["error"]["message"] == "Your account has been suspended."
    assert response.data["error"]["details"]["reason"] == (
        "Fraudulent activity detected"
    )
