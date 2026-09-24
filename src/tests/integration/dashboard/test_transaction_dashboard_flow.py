"""End-to-end transaction-to-dashboard integration coverage."""

from datetime import date
from typing import Any

import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
@freeze_time("2025-01-15 12:00:00")
def test_transaction_creation_refreshes_dashboard_overview() -> None:
    user: Any = UserFactory()
    client = APIClient()
    client.force_authenticate(user)

    created = client.post(
        reverse("api_v1:transactions:list"),
        {
            "amount": "42.50",
            "transaction_type": "expense",
            "category": "Food",
            "date": date(2025, 1, 15).isoformat(),
            "description": "Lunch",
        },
        format="json",
    )
    overview = client.get(reverse("api_v1:dashboard:overview"))

    assert created.status_code == 201
    assert overview.status_code == 200
    assert overview.data["as_of_date"] == "2025-01-15"
    assert overview.data["today"]["total_income"] == "0.00"
    assert overview.data["today"]["total_expense"] == "42.50"
    assert overview.data["today"]["net_balance"] == "-42.50"
    assert overview.data["this_week"]["net_balance"] == "-42.50"
    assert overview.data["this_month"]["net_balance"] == "-42.50"
