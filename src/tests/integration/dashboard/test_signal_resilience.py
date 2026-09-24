"""Signal resilience when the broker is temporarily unavailable."""

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from apps.dashboard.infrastructure.signals import invalidate_user_dashboard_cache
from apps.transactions.infrastructure.persistence.models import Transaction
from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_committed_transaction_does_not_fail_when_invalidation_publish_fails() -> None:
    user: Any = UserFactory()

    with patch.object(
        invalidate_user_dashboard_cache,
        "delay",
        side_effect=ConnectionError("broker unavailable"),
    ):
        transaction = Transaction.objects.create(
            user=user,
            amount=Decimal("10.00"),
            transaction_type="income",
            category="Salary",
            date=date(2025, 1, 15),
        )

    assert Transaction.objects.filter(pk=transaction.pk).exists()
    assert not DashboardSummary.objects.filter(user=user).exists()


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
def test_reassignment_invalidates_both_previous_and_new_owners() -> None:
    previous_owner: Any = UserFactory()
    new_owner: Any = UserFactory()
    transaction = Transaction.objects.create(
        user=previous_owner,
        amount=Decimal("10.00"),
        transaction_type="income",
        category="Salary",
        date=date(2025, 1, 15),
    )

    with patch.object(invalidate_user_dashboard_cache, "delay") as delay:
        transaction.user = new_owner
        transaction.save(update_fields=("user", "updated_at"))

    assert {(item.args[0], tuple(item.args[1])) for item in delay.call_args_list} == {
        (str(previous_owner.id), ("2025-01-15",)),
        (str(new_owner.id), ("2025-01-15",)),
    }
