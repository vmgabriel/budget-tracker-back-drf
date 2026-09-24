"""Authenticated dashboard HTTP interface tests."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from tests.factories import DashboardSummaryFactory, TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def test_dashboard_routes_are_mounted_under_api_v1() -> None:
    assert reverse("api_v1:dashboard:dashboard") == "/api/v1/dashboard/"
    assert reverse("api_v1:dashboard:overview") == "/api/v1/dashboard/overview/"
    assert reverse("api_v1:dashboard:daily") == "/api/v1/dashboard/daily/"
    assert reverse("api_v1:dashboard:weekly") == "/api/v1/dashboard/weekly/"
    assert reverse("api_v1:dashboard:monthly") == "/api/v1/dashboard/monthly/"


def test_dashboard_returns_precomputed_owner_summaries() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    summary: Any = DashboardSummaryFactory(
        user=owner,
        period="daily",
        date=date(2025, 1, 10),
        total_income=Decimal("500.00"),
        total_expense=Decimal("125.00"),
    )
    DashboardSummaryFactory(user=other_user, period="daily", date=date(2025, 1, 10))
    client = APIClient()
    client.force_authenticate(owner)

    response = client.get(
        reverse("api_v1:dashboard:daily"),
        {"start_date": "2025-01-01", "end_date": "2025-01-31"},
    )

    assert response.status_code == 200
    assert response.data["period"] == "daily"
    assert response.data["summary_count"] == 1
    assert response.data["has_stale_data"] is False
    assert response.data["summaries"][0]["id"] == str(summary.id)
    assert response.data["summaries"][0]["total_income"] == "500.00"
    assert response.data["summaries"][0]["total_expense"] == "125.00"
    assert response.data["summaries"][0]["net_balance"] == "375.00"
    assert response.data["summaries"][0]["status"] == "fresh"


@freeze_time("2025-01-15 12:00:00")
def test_dashboard_overview_returns_current_snapshots() -> None:
    user: Any = UserFactory()
    today = date(2025, 1, 15)
    DashboardSummaryFactory(
        user=user,
        period="daily",
        date=today,
        total_income=Decimal("25.00"),
        total_expense=Decimal("5.00"),
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(reverse("api_v1:dashboard:overview"))

    assert response.status_code == 200
    assert response.data["as_of_date"] == today.isoformat()
    assert response.data["today"]["net_balance"] == "20.00"
    assert response.data["this_week"] is None
    assert response.data["this_month"] is None


def test_dashboard_reports_stale_precomputed_data() -> None:
    user: Any = UserFactory()
    DashboardSummaryFactory(
        user=user,
        period="weekly",
        date=date(2025, 1, 6),
        is_stale=True,
        stale_at="2025-01-15T12:00:00Z",
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(
        reverse("api_v1:dashboard:weekly"),
        {"start_date": "2025-01-06", "end_date": "2025-01-12"},
    )

    assert response.status_code == 200
    assert response.data["has_stale_data"] is True
    assert response.data["summaries"][0]["status"] == "stale"
    assert response.data["summaries"][0]["stale_at"] is not None


def test_missing_summary_is_a_successful_empty_dashboard() -> None:
    user: Any = UserFactory()
    TransactionFactory(user=user)
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(reverse("api_v1:dashboard:dashboard"))

    assert response.status_code == 200
    assert response.data["is_empty"] is True
    assert response.data["summary_count"] == 0
    assert response.data["summaries"] == []
    assert not DashboardSummary.objects.filter(user=user).exists()


def test_dashboard_requires_authentication() -> None:
    client = APIClient()

    assert client.get(reverse("api_v1:dashboard:dashboard")).status_code == 403


def test_invalid_dashboard_queries_are_rejected() -> None:
    user: Any = UserFactory()
    client = APIClient()
    client.force_authenticate(user)

    reversed_range = client.get(
        reverse("api_v1:dashboard:daily"),
        {"start_date": "2025-02-01", "end_date": "2025-01-01"},
    )
    oversized_range = client.get(
        reverse("api_v1:dashboard:daily"),
        {"start_date": "2023-01-01", "end_date": "2024-03-01"},
    )
    wrong_fixed_period = client.get(
        reverse("api_v1:dashboard:daily"),
        {"period": "weekly"},
    )
    unknown_period = client.get(
        reverse("api_v1:dashboard:dashboard"),
        {"period": "yearly"},
    )

    assert reversed_range.status_code == 400
    assert oversized_range.status_code == 400
    assert wrong_fixed_period.status_code == 400
    assert unknown_period.status_code == 400


def test_dashboard_query_cannot_select_another_users_uuid() -> None:
    user: Any = UserFactory()
    other_user: Any = UserFactory()
    DashboardSummaryFactory(
        user=other_user,
        period="monthly",
        date=date(2025, 1, 1),
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(
        reverse("api_v1:dashboard:monthly"),
        {"user_id": str(other_user.id), "start_date": "2025-01-01"},
    )

    assert response.status_code == 200
    assert response.data["summary_count"] == 0
    assert str(uuid4()) not in str(response.data)
