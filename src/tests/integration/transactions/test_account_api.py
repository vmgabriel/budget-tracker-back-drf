"""Owner-scoped funding-account HTTP interface tests using JWT authentication."""

from typing import Any
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.transactions.infrastructure.persistence.models import Account, Transaction
from tests.factories import AccountFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _payload() -> dict[str, str]:
    return {"name": "Main Card", "account_type": "credit_card"}


def _authenticated_client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def test_api_v1_account_routes_are_mounted() -> None:
    account_id = uuid4()

    assert (
        reverse("api_v1:transactions:account-list") == "/api/v1/transactions/accounts/"
    )
    assert (
        reverse(
            "api_v1:transactions:account-detail",
            kwargs={"account_id": account_id},
        )
        == f"/api/v1/transactions/accounts/{account_id}/"
    )


def test_account_create_list_and_retrieve_are_owner_scoped(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    created = client.post(
        reverse("api_v1:transactions:account-list"), _payload(), format="json"
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["name"] == "Main Card"
    assert created.data["account_type"] == "credit_card"
    assert created.data["is_active"] is True
    assert Account.objects.get(pk=created.data["id"]).user_id == owner.id

    listing = client.get(reverse("api_v1:transactions:account-list"))
    assert listing.status_code == status.HTTP_200_OK
    assert listing.data["count"] == 1
    assert listing.data["results"][0]["id"] == created.data["id"]

    detail_url = reverse(
        "api_v1:transactions:account-detail",
        kwargs={"account_id": created.data["id"]},
    )
    retrieved = client.get(detail_url)
    assert retrieved.status_code == status.HTTP_200_OK
    assert retrieved.data["name"] == "Main Card"


def test_account_listing_hides_inactive_and_foreign_accounts(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    AccountFactory(user=owner, name="Visa")
    AccountFactory(user=owner, name="Old card", is_active=False)
    AccountFactory(user=other_user, name="Someone else")
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(reverse("api_v1:transactions:account-list"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["name"] == "Visa"


def test_other_users_cannot_retrieve_an_account(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    account: Any = AccountFactory(user=owner)
    client = _authenticated_client(other_user, jwt_token_factory)
    detail_url = reverse(
        "api_v1:transactions:account-detail", kwargs={"account_id": account.id}
    )

    assert client.get(detail_url).status_code == status.HTTP_404_NOT_FOUND


def test_account_endpoints_require_authentication() -> None:
    client = APIClient()

    assert (
        client.get(reverse("api_v1:transactions:account-list")).status_code
        == status.HTTP_401_UNAUTHORIZED
    )
    assert (
        client.post(
            reverse("api_v1:transactions:account-list"), _payload(), format="json"
        ).status_code
        == status.HTTP_401_UNAUTHORIZED
    )


def test_invalid_account_payloads_are_rejected(jwt_token_factory: Any) -> None:
    user: Any = UserFactory()
    client = _authenticated_client(user, jwt_token_factory)
    invalid_payloads = (
        {**_payload(), "name": ""},
        {**_payload(), "name": "   "},
        {**_payload(), "name": "x" * 101},
        {**_payload(), "account_type": "credit"},
        {**_payload(), "account_type": ""},
    )

    for payload in invalid_payloads:
        response = client.post(
            reverse("api_v1:transactions:account-list"), payload, format="json"
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    assert not Account.objects.exists()


def test_transaction_create_and_patch_carry_a_flat_account_reference(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    account: Any = AccountFactory(user=owner, name="Checking")
    client = _authenticated_client(owner, jwt_token_factory)

    created = client.post(
        reverse("api_v1:transactions:list"),
        {
            "amount": "42.50",
            "transaction_type": "expense",
            "category": "Groceries",
            "date": "2025-01-10",
            "account_id": str(account.id),
        },
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["account_id"] == str(account.id)
    assert created.data["account_name"] == "Checking"

    detail_url = reverse(
        "api_v1:transactions:detail", kwargs={"transaction_id": created.data["id"]}
    )
    updated = client.patch(
        detail_url,
        {"amount": "50.00", "account_id": str(account.id)},
        format="json",
    )
    assert updated.status_code == status.HTTP_200_OK
    assert updated.data["account_id"] == str(account.id)
    assert updated.data["account_name"] == "Checking"

    listing = client.get(reverse("api_v1:transactions:list"))
    assert listing.data["results"][0]["account_id"] == str(account.id)
    assert listing.data["results"][0]["account_name"] == "Checking"


def test_transactions_without_an_account_expose_null_fields(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    client = _authenticated_client(owner, jwt_token_factory)

    created = client.post(
        reverse("api_v1:transactions:list"),
        {
            "amount": "10.00",
            "transaction_type": "expense",
            "category": "Coffee",
            "date": "2025-01-10",
        },
        format="json",
    )

    assert created.status_code == status.HTTP_201_CREATED
    assert created.data["account_id"] is None
    assert created.data["account_name"] is None


def test_transactions_reject_foreign_or_unknown_accounts(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    foreign_account: Any = AccountFactory(user=other_user)
    client = _authenticated_client(owner, jwt_token_factory)
    payload = {
        "amount": "42.50",
        "transaction_type": "expense",
        "category": "Groceries",
        "date": "2025-01-10",
        "account_id": str(foreign_account.id),
    }

    foreign = client.post(reverse("api_v1:transactions:list"), payload, format="json")
    unknown = client.post(
        reverse("api_v1:transactions:list"),
        {**payload, "account_id": str(uuid4())},
        format="json",
    )

    assert foreign.status_code == status.HTTP_404_NOT_FOUND
    assert unknown.status_code == status.HTTP_404_NOT_FOUND
    assert not Transaction.objects.exists()


def test_deleting_an_account_detaches_its_transactions(
    jwt_token_factory: Any,
) -> None:
    owner: Any = UserFactory()
    account: Any = AccountFactory(user=owner)
    client = _authenticated_client(owner, jwt_token_factory)
    created = client.post(
        reverse("api_v1:transactions:list"),
        {
            "amount": "42.50",
            "transaction_type": "expense",
            "category": "Groceries",
            "date": "2025-01-10",
            "account_id": str(account.id),
        },
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED

    account.delete()

    detail = client.get(
        reverse(
            "api_v1:transactions:detail",
            kwargs={"transaction_id": created.data["id"]},
        )
    )
    assert detail.status_code == status.HTTP_200_OK
    assert detail.data["account_id"] is None
    assert detail.data["account_name"] is None
