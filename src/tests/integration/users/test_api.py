"""HTTP interface tests for authentication and user management."""

from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.domain.value_objects import PlanLevel
from tests.factories import UserFactory

User = get_user_model()
pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_api_v1_routes_keep_existing_user_paths() -> None:
    assert reverse("api_v1:users:register") == "/api/v1/auth/register/"
    assert reverse("api_v1:users:admin-list") == "/api/v1/users/"


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

    assert registration.status_code == 201
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
    assert login.status_code == 200

    me = client.get(reverse("api_v1:users:me"))
    assert me.status_code == 200
    assert me.data["email"] == "new-user@example.com"

    logout = client.post(reverse("api_v1:users:logout"))
    assert logout.status_code == 204
    assert client.get(reverse("api_v1:users:me")).status_code == 403


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

    assert response.status_code == 400
    assert "email" in response.data


def test_admin_can_list_and_change_plan_but_regular_user_cannot() -> None:
    target: Any = UserFactory(email="target@example.com")
    regular_user = UserFactory(email="regular@example.com")
    administrator = UserFactory(email="admin@example.com", is_staff=True)
    client = APIClient()

    client.force_authenticate(regular_user)
    forbidden = client.get(reverse("api_v1:users:admin-list"))
    assert forbidden.status_code == 403

    client.force_authenticate(administrator)
    listing = client.get(reverse("api_v1:users:admin-list"))
    assert listing.status_code == 200
    assert listing.data["count"] >= 3

    plan_response = client.patch(
        reverse("api_v1:users:admin-plan", kwargs={"user_id": target.id}),
        {"plan": PlanLevel.PREMIUM.value},
        format="json",
    )
    assert plan_response.status_code == 200
    target.refresh_from_db()
    assert target.plan == PlanLevel.PREMIUM.value

    profile_response = client.patch(
        reverse("api_v1:users:admin-detail", kwargs={"user_id": target.id}),
        {
            "email": "updated-target@example.com",
            "full_name": "Updated Target",
            "is_active": False,
        },
        format="json",
    )
    assert profile_response.status_code == 200
    target.refresh_from_db()
    assert target.email == "updated-target@example.com"
    assert target.full_name == "Updated Target"
    assert target.is_active is False
