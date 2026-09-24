"""Celery dashboard task and transaction-signal integration tests."""

from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import call, patch

import pytest
from celery.exceptions import Retry
from django.db import OperationalError
from freezegun import freeze_time

from apps.dashboard.domain.value_objects import Period, SummaryDate
from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from apps.dashboard.infrastructure.persistence.repositories import (
    DjangoDashboardSummaryRepository,
)
from apps.dashboard.infrastructure.tasks import (
    generate_daily_summary,
    generate_monthly_summary,
    generate_weekly_summary,
    reconcile_user_dashboards,
)
from apps.transactions.infrastructure.persistence.models import Transaction
from tests.factories import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


@freeze_time("2025-01-15 12:00:00")
def test_celery_app_registers_dashboard_tasks(celery_app: Any) -> None:
    assert (
        "apps.dashboard.infrastructure.tasks.generate_daily_summary" in celery_app.tasks
    )
    assert (
        "apps.dashboard.infrastructure.tasks.generate_weekly_summary"
        in celery_app.tasks
    )
    assert (
        "apps.dashboard.infrastructure.tasks.generate_monthly_summary"
        in celery_app.tasks
    )
    assert (
        "apps.dashboard.infrastructure.tasks.reconcile_user_dashboards"
        in celery_app.tasks
    )


@freeze_time("2025-01-15 12:00:00")
def test_reconciliation_enqueues_current_month_for_active_users() -> None:
    user: Any = UserFactory()
    UserFactory(is_active=False)

    with patch.object(generate_monthly_summary, "delay") as delay:
        result = reconcile_user_dashboards.run()

    assert result["users"] == 1
    assert result["jobs_enqueued"] == 1
    delay.assert_called_once_with(str(user.id), "2025-01-15")


@freeze_time("2025-02-01 12:00:00")
def test_weekly_task_refreshes_each_month_touched_by_its_week() -> None:
    user: Any = UserFactory()

    with patch.object(generate_monthly_summary, "delay") as delay:
        generate_weekly_summary.run(str(user.id), "2025-01-27")

    assert delay.call_args_list == [
        call(str(user.id), "2025-01-01"),
        call(str(user.id), "2025-02-01"),
    ]


def test_daily_task_builds_rollups_and_is_idempotent() -> None:
    user: Any = UserFactory()
    Transaction.objects.bulk_create(
        (
            Transaction(
                user=user,
                amount=Decimal("500.00"),
                transaction_type="income",
                category="Salary",
                date=date(2025, 1, 15),
            ),
            Transaction(
                user=user,
                amount=Decimal("125.00"),
                transaction_type="expense",
                category="Rent",
                date=date(2025, 1, 15),
            ),
        )
    )
    repository = DjangoDashboardSummaryRepository()

    first = generate_daily_summary.delay(str(user.id), "2025-01-15")
    first_count = DashboardSummary.objects.filter(user=user).count()
    second = generate_daily_summary.delay(str(user.id), "2025-01-15")

    daily = repository.get(
        user.id,
        Period.DAILY,
        SummaryDate(date(2025, 1, 15)),
    )
    weekly = repository.get(
        user.id,
        Period.WEEKLY,
        SummaryDate(date(2025, 1, 13)),
    )
    monthly = repository.get(
        user.id,
        Period.MONTHLY,
        SummaryDate(date(2025, 1, 1)),
    )

    assert first.successful()
    assert second.successful()
    assert first_count == DashboardSummary.objects.filter(user=user).count()
    assert daily is not None and daily.total_income.amount == Decimal("500.00")
    assert daily.total_expense.amount == Decimal("125.00")
    assert weekly is not None and weekly.net_balance.amount == Decimal("375.00")
    assert monthly is not None and monthly.net_balance.amount == Decimal("375.00")
    assert not monthly.is_stale


@freeze_time("2025-01-15 12:00:00")
def test_transaction_create_update_and_delete_refresh_summaries() -> None:
    user: Any = UserFactory()
    transaction = Transaction.objects.create(
        user=user,
        amount=Decimal("100.00"),
        transaction_type="income",
        category="Salary",
        date=date(2025, 1, 15),
    )
    repository = DjangoDashboardSummaryRepository()

    def daily_totals() -> tuple[Decimal, Decimal]:
        summary = repository.get(
            user.id,
            Period.DAILY,
            SummaryDate(date(2025, 1, 15)),
        )
        assert summary is not None
        return summary.total_income.amount, summary.total_expense.amount

    assert daily_totals() == (Decimal("100.00"), Decimal("0.00"))

    transaction.transaction_type = "expense"
    transaction.amount = Decimal("30.00")
    transaction.save()
    assert daily_totals() == (Decimal("0.00"), Decimal("30.00"))

    transaction.date = date(2025, 1, 14)
    transaction.save()
    assert daily_totals() == (Decimal("0.00"), Decimal("0.00"))

    transaction.delete()
    assert daily_totals() == (Decimal("0.00"), Decimal("0.00"))


@freeze_time("2025-03-15 12:00:00")
def test_monthly_task_corrects_weekly_rows_at_month_boundaries() -> None:
    user: Any = UserFactory()
    Transaction.objects.bulk_create(
        (
            Transaction(
                user=user,
                amount=Decimal("31.00"),
                transaction_type="income",
                category="January",
                date=date(2025, 1, 31),
            ),
            Transaction(
                user=user,
                amount=Decimal("70.00"),
                transaction_type="income",
                category="February start",
                date=date(2025, 2, 1),
            ),
            Transaction(
                user=user,
                amount=Decimal("30.00"),
                transaction_type="expense",
                category="February end",
                date=date(2025, 2, 28),
            ),
        )
    )

    result = generate_monthly_summary.delay(str(user.id), "2025-02-15")
    repository = DjangoDashboardSummaryRepository()

    february = repository.get(
        user.id,
        Period.MONTHLY,
        SummaryDate(date(2025, 2, 1)),
    )
    boundary_week = repository.get(
        user.id,
        Period.WEEKLY,
        SummaryDate(date(2025, 1, 27)),
    )

    assert result.successful()
    assert february is not None
    assert february.total_income.amount == Decimal("70.00")
    assert february.total_expense.amount == Decimal("30.00")
    assert february.net_balance.amount == Decimal("40.00")
    assert boundary_week is not None and not boundary_week.is_stale


@freeze_time("2025-01-15 12:00:00")
def test_transient_database_errors_are_retried() -> None:
    user: Any = UserFactory()

    with (
        patch.object(
            DjangoDashboardSummaryRepository,
            "mark_stale",
            side_effect=OperationalError("temporary database failure"),
        ) as mark_stale,
        patch.object(
            generate_daily_summary,
            "retry",
            side_effect=Retry(),
        ) as retry,
        pytest.raises(Retry),
    ):
        generate_daily_summary.run(str(user.id), "2025-01-15")

    assert mark_stale.call_count == 1
    retry.assert_called_once()
    assert isinstance(retry.call_args.kwargs["exc"], OperationalError)
