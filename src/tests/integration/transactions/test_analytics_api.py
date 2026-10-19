"""Bounded analytics HTTP interface tests using JWT authentication."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.transactions.domain.value_objects import TransactionType
from tests.factories import TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

URL_NAME = "api_v1:transactions:analytics"


def _authenticated_client(user: Any, token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_factory(user)}")
    return client


def _seed() -> tuple[Any, Any]:
    """Create two months of data spread across days, categories, and types."""
    owner: Any = UserFactory()
    other: Any = UserFactory()
    rows = (
        (owner, date(2025, 1, 6), TransactionType.EXPENSE, "Food", "10.00"),
        (owner, date(2025, 1, 8), TransactionType.EXPENSE, "Food", "20.00"),
        (owner, date(2025, 1, 20), TransactionType.EXPENSE, "Rent", "800.00"),
        (owner, date(2025, 2, 3), TransactionType.INCOME, "Salary", "1000.00"),
        (owner, date(2025, 2, 4), TransactionType.INVESTMENT, "Index", "200.00"),
        (owner, date(2025, 2, 5), TransactionType.SAVINGS, "Emergency", "50.00"),
        (other, date(2025, 1, 6), TransactionType.EXPENSE, "Food", "999.00"),
    )
    for user, day, kind, category, amount in rows:
        TransactionFactory(
            user=user,
            date=day,
            transaction_type=kind.value,
            category=category,
            amount=Decimal(amount),
        )
    return owner, other


def test_analytics_route_is_mounted() -> None:
    assert reverse(URL_NAME) == "/api/v1/transactions/analytics/"


def test_category_analytics_returns_flat_chart_data(jwt_token_factory: Any) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "category",
            "period": "monthly",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "period": "monthly",
        "group_by": "category",
        "data": [
            {"label": "Rent", "total": "800.00"},
            {"label": "Food", "total": "30.00"},
        ],
    }


def test_type_analytics_returns_all_four_series(jwt_token_factory: Any) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "type",
            "period": "monthly",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {
        "period": "monthly",
        "group_by": "type",
        "data": [
            {
                "label": "2025-01",
                "income": "0.00",
                "expense": "830.00",
                "investment": "0.00",
                "savings": "0.00",
            },
            {
                "label": "2025-02",
                "income": "1000.00",
                "expense": "0.00",
                "investment": "200.00",
                "savings": "50.00",
            },
        ],
    }


def test_weekly_analytics_uses_iso_week_labels(jwt_token_factory: Any) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "type",
            "period": "weekly",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert [row["label"] for row in response.data["data"]] == [
        "2025-W02",
        "2025-W04",
        "2025-W06",
    ]


def test_period_defaults_to_monthly(jwt_token_factory: Any) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "type",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["period"] == "monthly"
    assert len(response.data["data"]) == 2


def test_analytics_is_owner_scoped(jwt_token_factory: Any) -> None:
    _, other = _seed()
    client = _authenticated_client(other, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "category",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"] == [{"label": "Food", "total": "999.00"}]


def test_analytics_rejects_ranges_longer_than_one_year(
    jwt_token_factory: Any,
) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2026-01-03",
            "group_by": "type",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"
    assert "366" in response.data["detail"]


@pytest.mark.parametrize(
    "params",
    [
        {"end_date": "2025-02-28", "group_by": "type"},
        {"start_date": "2025-01-01", "group_by": "type"},
        {"start_date": "2025-01-01", "end_date": "2025-02-28"},
        {"start_date": "2025-01-01", "end_date": "2025-02-28", "group_by": "account"},
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "type",
            "period": "yearly",
        },
        {
            "start_date": "2025-02-28",
            "end_date": "2025-01-01",
            "group_by": "type",
        },
    ],
)
def test_analytics_rejects_invalid_query_parameters(
    jwt_token_factory: Any, params: dict[str, str]
) -> None:
    owner, _ = _seed()
    client = _authenticated_client(owner, jwt_token_factory)

    response = client.get(reverse(URL_NAME), params)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["error"]["code"] == "validation_error"


def test_analytics_requires_authentication() -> None:
    response = APIClient().get(
        reverse(URL_NAME),
        {
            "start_date": "2025-01-01",
            "end_date": "2025-02-28",
            "group_by": "type",
        },
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
