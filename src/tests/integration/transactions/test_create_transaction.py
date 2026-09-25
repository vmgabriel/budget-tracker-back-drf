"""JWT-authenticated transaction creation coverage."""

from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_create_transaction_with_jwt(jwt_token_factory: Any) -> None:
    user = UserFactory()
    access_token = jwt_token_factory(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    response = client.post(
        reverse("api_v1:transactions:list"),
        {
            "amount": "100.00",
            "transaction_type": "income",
            "category": "salary",
            "date": "2025-01-10",
            "description": "Test transaction",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
