"""Dashboard backfill command integration test."""

from datetime import date
from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from freezegun import freeze_time

from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from apps.transactions.infrastructure.persistence.models import Transaction
from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db
@freeze_time("2025-01-15 12:00:00")
def test_rebuild_dashboard_repairs_bulk_imported_transactions() -> None:
    user: Any = UserFactory()
    today = date(2025, 1, 15)
    Transaction.objects.bulk_create(
        (
            Transaction(
                user=user,
                amount=Decimal("12.00"),
                transaction_type="income",
                category="Salary",
                date=today,
                description="[bulk-import]",
            ),
        )
    )

    call_command("rebuild_dashboard", months=1, stdout=StringIO())

    summary = DashboardSummary.objects.get(
        user=user,
        period="daily",
        date=today,
    )
    assert summary.total_income == Decimal("12.00")
    assert not summary.is_stale
