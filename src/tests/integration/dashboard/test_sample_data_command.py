"""Sample-data management command integration test."""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from apps.transactions.infrastructure.persistence.models import Transaction


@pytest.mark.integration
@pytest.mark.django_db
def test_create_sample_data_is_idempotent_and_generates_summaries() -> None:
    output = StringIO()

    call_command("create_sample_data", months=1, stdout=output)
    first_transaction_count = Transaction.objects.count()
    first_summary_count = DashboardSummary.objects.count()

    call_command("create_sample_data", months=1, stdout=output)

    sample_users = get_user_model().objects.filter(
        email__in=[
            "demo-free@example.com",
            "demo-pro@example.com",
            "demo-premium@example.com",
        ]
    )
    assert sample_users.count() == 3
    assert set(sample_users.values_list("plan", flat=True)) == {
        "free",
        "pro",
        "premium",
    }
    assert Transaction.objects.count() == first_transaction_count
    assert DashboardSummary.objects.count() == first_summary_count
    assert first_transaction_count > 0
    assert first_summary_count > 0
    assert not DashboardSummary.objects.filter(is_stale=True).exists()
    assert "Sample login password" in output.getvalue()


@pytest.mark.integration
@pytest.mark.django_db
@override_settings(ENVIRONMENT="production")
def test_create_sample_data_refuses_production_settings() -> None:
    with pytest.raises(CommandError, match="disabled in production"):
        call_command("create_sample_data", months=1, verbosity=0)
