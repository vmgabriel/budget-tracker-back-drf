"""Owner-scoped transaction HTTP interface tests."""

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.transactions.infrastructure.persistence.models import Transaction
from tests.factories import TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _payload() -> dict[str, str]:
    return {
        "amount": "42.50",
        "transaction_type": "expense",
        "category": "Food",
        "date": "2025-01-10",
        "description": "Lunch",
    }


def test_api_v1_routes_keep_existing_transaction_paths() -> None:
    transaction_id = uuid4()

    assert reverse("api_v1:transactions:list") == "/api/v1/transactions/"
    assert (
        reverse(
            "api_v1:transactions:detail",
            kwargs={"transaction_id": transaction_id},
        )
        == f"/api/v1/transactions/{transaction_id}/"
    )


def test_transaction_crud_is_authenticated_and_owner_scoped() -> None:
    owner: Any = UserFactory()
    client = APIClient()
    client.force_authenticate(owner)

    created = client.post(
        reverse("api_v1:transactions:list"), _payload(), format="json"
    )

    assert created.status_code == 201
    assert created.data["amount"] == "42.50"
    assert created.data["transaction_type"] == "expense"
    assert created.data["description"] == "Lunch"
    assert Transaction.objects.get(pk=created.data["id"]).user_id == owner.id

    listing = client.get(reverse("api_v1:transactions:list"))
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    assert listing.data["results"][0]["id"] == created.data["id"]

    detail_url = reverse(
        "api_v1:transactions:detail", kwargs={"transaction_id": created.data["id"]}
    )
    retrieved = client.get(detail_url)
    assert retrieved.status_code == 200
    assert retrieved.data["category"] == "Food"

    updated = client.patch(
        detail_url,
        {
            "amount": "99.95",
            "transaction_type": "savings",
            "category": "Emergency Fund",
            "date": "2025-01-12",
            "description": "",
        },
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["amount"] == "99.95"
    assert updated.data["transaction_type"] == "savings"
    assert updated.data["category"] == "Emergency Fund"
    assert updated.data["description"] is None

    deleted = client.delete(detail_url)
    assert deleted.status_code == 204
    assert not Transaction.objects.filter(pk=created.data["id"]).exists()


def test_transaction_endpoints_require_authentication() -> None:
    client = APIClient()

    assert client.get(reverse("api_v1:transactions:list")).status_code == 403
    assert (
        client.post(
            reverse("api_v1:transactions:list"), _payload(), format="json"
        ).status_code
        == 403
    )


def test_other_users_cannot_read_update_or_delete_transaction() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    transaction: Any = TransactionFactory(user=owner)
    client = APIClient()
    client.force_authenticate(other_user)
    detail_url = reverse(
        "api_v1:transactions:detail", kwargs={"transaction_id": transaction.id}
    )

    assert client.get(detail_url).status_code == 404
    assert (
        client.patch(detail_url, {"amount": "1.00"}, format="json").status_code == 404
    )
    assert client.delete(detail_url).status_code == 404
    assert Transaction.objects.filter(pk=transaction.pk).exists()


def test_listing_is_paginated_and_does_not_leak_other_users() -> None:
    owner = UserFactory()
    other_user = UserFactory()
    TransactionFactory(user=owner, date=date(2025, 1, 9))
    expected_first: Any = TransactionFactory(user=owner, date=date(2025, 1, 12))
    TransactionFactory(user=other_user, date=date(2025, 1, 15))
    client = APIClient()
    client.force_authenticate(owner)

    response = client.get(reverse("api_v1:transactions:list"), {"page_size": 1})

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["page_size"] == 1
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] == str(expected_first.id)


def test_invalid_pagination_is_rejected() -> None:
    user: Any = UserFactory()
    client = APIClient()
    client.force_authenticate(user)

    non_numeric = client.get(reverse("api_v1:transactions:list"), {"page": "first"})
    oversized_page = client.get(
        reverse("api_v1:transactions:list"), {"page": 1_000_000_000}
    )
    out_of_range = client.get(reverse("api_v1:transactions:list"), {"page_size": 101})

    assert non_numeric.status_code == 400
    assert oversized_page.status_code == 400
    assert out_of_range.status_code == 400


def test_invalid_transaction_payloads_are_rejected() -> None:
    user: Any = UserFactory()
    client = APIClient()
    client.force_authenticate(user)
    future_date = (date.today() + timedelta(days=30)).isoformat()
    invalid_payloads = (
        {**_payload(), "amount": "0.00"},
        {**_payload(), "amount": "1.234"},
        {**_payload(), "amount": "10000000000.00"},
        {**_payload(), "transaction_type": "transfer"},
        {**_payload(), "category": "   "},
        {**_payload(), "date": future_date},
    )

    for payload in invalid_payloads:
        response = client.post(
            reverse("api_v1:transactions:list"), payload, format="json"
        )
        assert response.status_code == 400

    assert not Transaction.objects.exists()
