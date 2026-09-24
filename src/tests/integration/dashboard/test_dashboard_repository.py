"""Django ORM adapter tests for dashboard summaries and transaction reads."""

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError
from django.db import transaction as db_transaction
from django.utils import timezone

from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
)
from apps.dashboard.infrastructure.persistence.models import (
    DashboardSummary as SummaryModel,
)
from apps.dashboard.infrastructure.persistence.repositories import (
    DjangoDashboardSummaryRepository,
    DjangoTransactionReadRepository,
)
from tests.factories import TransactionFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _summary(user: Any, *, period: Period, summary_date: date) -> DashboardSummary:
    totals = PeriodTotals(
        income=TotalIncome(Decimal("100.00")),
        expense=TotalExpense(Decimal("25.00")),
        net_balance=NetBalance(Decimal("75.00")),
    )
    return DashboardSummary.create(
        user_id=user.id,
        period=period,
        summary_date=period.start(SummaryDate(summary_date)),
        totals=totals,
        generated_at=timezone.now(),
    )


def test_summary_repository_round_trips_and_scopes_queries() -> None:
    owner: Any = UserFactory()
    other_user: Any = UserFactory()
    repository = DjangoDashboardSummaryRepository()
    daily = _summary(owner, period=Period.DAILY, summary_date=date(2025, 1, 10))
    weekly = _summary(owner, period=Period.WEEKLY, summary_date=date(2025, 1, 6))
    repository.save(
        _summary(other_user, period=Period.DAILY, summary_date=date(2025, 1, 11))
    )

    saved = repository.save(daily)
    repository.save(weekly)
    loaded = repository.get(owner.id, Period.DAILY, SummaryDate(date(2025, 1, 10)))
    listed = repository.list_for_user(
        owner.id,
        Period.DAILY,
        date(2025, 1, 1),
        date(2025, 1, 31),
    )
    other_listed = repository.list_for_user(
        other_user.id,
        Period.DAILY,
        date(2025, 1, 1),
        date(2025, 1, 31),
    )

    assert saved.id is not None
    assert loaded is not None
    assert loaded.id == saved.id
    assert loaded.net_balance.amount == Decimal("75.00")
    assert [item.summary_date.value for item in listed] == [date(2025, 1, 10)]
    assert len(other_listed) == 1
    assert other_listed[0].id != saved.id


def test_summary_save_is_idempotent_on_natural_key() -> None:
    user: Any = UserFactory()
    repository = DjangoDashboardSummaryRepository()
    original = _summary(user, period=Period.DAILY, summary_date=date(2025, 1, 10))

    first = repository.save(original)
    second = repository.save(original)

    assert first.id == second.id
    assert SummaryModel.objects.filter(user=user, period="daily").count() == 1


def test_mark_stale_is_owner_scoped_and_idempotent() -> None:
    user: Any = UserFactory()
    other_user: Any = UserFactory()
    repository = DjangoDashboardSummaryRepository()
    for owner in (user, other_user):
        for period in Period:
            repository.save(
                _summary(
                    owner,
                    period=period,
                    summary_date=date(2025, 1, 15),
                )
            )
    periods = {
        (period, period.start(SummaryDate(date(2025, 1, 15)))) for period in Period
    }

    assert repository.mark_stale(user.id, periods, timezone.now()) == 3
    assert repository.mark_stale(user.id, periods, timezone.now()) == 0
    assert not SummaryModel.objects.filter(user=user, is_stale=False).exists()
    assert not SummaryModel.objects.filter(user=other_user, is_stale=True).exists()


def test_transaction_read_repository_aggregates_only_income_and_expense() -> None:
    user: Any = UserFactory()
    other_user: Any = UserFactory()
    target_date = date(2025, 1, 10)
    TransactionFactory(
        user=user,
        date=target_date,
        amount=Decimal("100.00"),
        transaction_type="income",
    )
    TransactionFactory(
        user=user,
        date=target_date,
        amount=Decimal("30.00"),
        transaction_type="expense",
    )
    TransactionFactory(
        user=user,
        date=target_date,
        amount=Decimal("50.00"),
        transaction_type="investment",
    )
    TransactionFactory(
        user=user,
        date=target_date,
        amount=Decimal("20.00"),
        transaction_type="savings",
    )
    TransactionFactory(
        user=other_user,
        date=target_date,
        amount=Decimal("999.00"),
        transaction_type="income",
    )

    totals = DjangoTransactionReadRepository().aggregate_totals(
        user.id,
        target_date,
        target_date,
    )

    assert totals.income.amount == Decimal("100.00")
    assert totals.expense.amount == Decimal("30.00")
    assert totals.net_balance.amount == Decimal("70.00")


def test_database_rejects_inconsistent_summary_totals() -> None:
    user: Any = UserFactory()

    with pytest.raises(IntegrityError), db_transaction.atomic():
        SummaryModel.objects.create(
            user=user,
            period="daily",
            date=date(2025, 1, 10),
            total_income=Decimal("10.00"),
            total_expense=Decimal("2.00"),
            net_balance=Decimal("9.00"),
            is_stale=False,
            generated_at=timezone.now(),
            stale_at=None,
        )
