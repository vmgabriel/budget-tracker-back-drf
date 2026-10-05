"""Owner-scoped rentals HTTP interface tests using JWT authentication."""

from typing import Any
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import (
    ApartmentFactory,
    DocumentFactory,
    HouseFactory,
    UserFactory,
    UtilityReadingFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _authenticated_client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def _create_house_via_api(client: APIClient) -> Any:
    response = client.post(
        reverse("api_v1:rentals:house-list"),
        {
            "name": "Maple House",
            "street": "1 Main St",
            "city": "Springfield",
            "state": "IL",
            "country": "US",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


def _create_apartment_via_api(client: APIClient, house_id: str) -> Any:
    response = client.post(
        reverse("api_v1:rentals:apartment-list"),
        {
            "house_id": house_id,
            "number": "101",
            "floor": 2,
            "monthly_rent": "500.00",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return response.data


def test_rentals_endpoints_require_authentication() -> None:
    client = APIClient()

    assert (
        client.get(reverse("api_v1:rentals:house-list")).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    missing = uuid4()
    assert (
        client.get(
            reverse("api_v1:rentals:house-detail", kwargs={"pk": missing})
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_house_and_apartment_crud_flow(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    house = _create_house_via_api(client)
    assert house["name"] == "Maple House"
    assert house["street"] == "1 Main St"

    listing = client.get(reverse("api_v1:rentals:house-list"))
    assert listing.status_code == status.HTTP_200_OK
    assert len(listing.data) == 1

    apartment = _create_apartment_via_api(client, house["id"])
    assert apartment["number"] == "101"
    assert apartment["floor"] == 2
    assert apartment["monthly_rent"] == "500.00"

    apartments = client.get(
        reverse("api_v1:rentals:apartment-list"), {"house_id": house["id"]}
    )
    assert apartments.status_code == status.HTTP_200_OK
    assert len(apartments.data) == 1

    updated = client.patch(
        reverse("api_v1:rentals:apartment-detail", kwargs={"pk": apartment["id"]}),
        {"monthly_rent": "550.00"},
        format="json",
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.data["monthly_rent"] == "550.00"


def test_house_is_not_visible_to_other_users(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    house: Any = HouseFactory(owner=owner)
    client = _authenticated_client(other, jwt_token_factory)

    response = client.get(
        reverse("api_v1:rentals:house-detail", kwargs={"pk": house.id})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_nested_resources_are_hidden_from_other_users(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    other: Any = UserFactory()
    apartment: Any = ApartmentFactory(house__owner=owner)
    document: Any = DocumentFactory(apartment=apartment)
    reading: Any = UtilityReadingFactory(apartment=apartment)
    foreign = _authenticated_client(other, jwt_token_factory)

    assert (
        foreign.get(
            reverse("api_v1:rentals:apartment-detail", kwargs={"pk": apartment.id})
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse(
                "api_v1:rentals:document-list", kwargs={"apartment_id": apartment.id}
            )
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse("api_v1:rentals:document-detail", kwargs={"pk": document.id})
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse(
                "api_v1:rentals:utility-reading-list",
                kwargs={"apartment_id": apartment.id},
            )
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse("api_v1:rentals:utility-reading-detail", kwargs={"pk": reading.id})
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse(
                "api_v1:rentals:payment-list", kwargs={"apartment_id": apartment.id}
            )
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse(
                "api_v1:rentals:utility-bill",
                kwargs={"apartment_id": apartment.id},
            ),
            {"utility_type": "WATER", "year": 2026, "month": 1},
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        foreign.get(
            reverse(
                "api_v1:rentals:payment-summary",
                kwargs={"apartment_id": apartment.id},
            ),
            {"year": 2026, "month": 1},
        ).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_utility_reading_calculates_consumption_and_total(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)
    house = _create_house_via_api(client)
    apartment = _create_apartment_via_api(client, house["id"])

    created = client.post(
        reverse(
            "api_v1:rentals:utility-reading-list",
            kwargs={"apartment_id": apartment["id"]},
        ),
        {
            "utility_type": "WATER",
            "reading_date": "2026-01-31",
            "current_reading": "120.50",
            "previous_reading": "100.00",
            "unit_cost": "0.5000",
        },
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["consumption"] == "20.50"
    assert created.data["total_cost"] == "10.25"

    bill = client.get(
        reverse(
            "api_v1:rentals:utility-bill",
            kwargs={"apartment_id": apartment["id"]},
        ),
        {"utility_type": "WATER", "year": 2026, "month": 1},
    )
    assert bill.status_code == status.HTTP_200_OK
    assert bill.data["total_consumption"] == "20.50"
    assert bill.data["total_cost"] == "10.25"
    assert bill.data["reading_count"] == 1


def test_duplicate_utility_reading_returns_400(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)
    house = _create_house_via_api(client)
    apartment = _create_apartment_via_api(client, house["id"])
    url = reverse(
        "api_v1:rentals:utility-reading-list", kwargs={"apartment_id": apartment["id"]}
    )
    payload = {
        "utility_type": "WATER",
        "reading_date": "2026-01-31",
        "current_reading": "120.50",
        "previous_reading": "100.00",
        "unit_cost": "0.5000",
    }

    first = client.post(url, payload, format="json")
    assert first.status_code == status.HTTP_201_CREATED

    duplicate = client.post(url, payload, format="json")
    assert duplicate.status_code == status.HTTP_400_BAD_REQUEST


def test_payment_status_auto_calculated_and_summary_aggregates(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)
    house = _create_house_via_api(client)
    apartment = _create_apartment_via_api(client, house["id"])

    created = client.post(
        reverse(
            "api_v1:rentals:payment-list", kwargs={"apartment_id": apartment["id"]}
        ),
        {"payment_date": "2026-01-05", "amount": "300.00", "notes": "deposit"},
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["status"] == "PARTIAL"

    summary = client.get(
        reverse(
            "api_v1:rentals:payment-summary",
            kwargs={"apartment_id": apartment["id"]},
        ),
        {"year": 2026, "month": 1},
    )
    assert summary.status_code == status.HTTP_200_OK
    assert summary.data["total_paid"] == "300.00"
    assert summary.data["outstanding_balance"] == "200.00"
    assert summary.data["payment_count"] == 1

    updated = client.patch(
        reverse("api_v1:rentals:payment-detail", kwargs={"pk": created.data["id"]}),
        {"amount": "500.00"},
        format="json",
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.data["status"] == "PAID"


def test_document_upload_and_list(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)
    house = _create_house_via_api(client)
    apartment = _create_apartment_via_api(client, house["id"])

    created = client.post(
        reverse(
            "api_v1:rentals:document-list", kwargs={"apartment_id": apartment["id"]}
        ),
        {
            "document_type": "LEASE_CONTRACT",
            "file_url": "https://files.example.com/lease.pdf",
            "description": "Signed by both parties",
        },
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["document_type"] == "LEASE_CONTRACT"

    listing = client.get(
        reverse(
            "api_v1:rentals:document-list", kwargs={"apartment_id": apartment["id"]}
        )
    )
    assert listing.status_code == status.HTTP_200_OK
    assert len(listing.data) == 1
