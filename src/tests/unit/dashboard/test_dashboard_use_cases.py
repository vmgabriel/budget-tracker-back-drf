"""Dashboard application use-case tests."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.dashboard.application.exceptions import (
    InvalidDashboardQuery,
)
from apps.dashboard.application.use_cases import (
    GenerateDashboardSummary,
    GenerateDashboardSummaryCommand,
    GetDashboardOverview,
    GetUserDashboard,
    GetUserDashboardCommand,
    InvalidateUserCache,
    InvalidateUserCacheCommand,
)
from apps.dashboard.domain.exceptions import DashboardSummaryImmutable
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    TotalExpense,
    TotalIncome,
)

from .fakes import (
    FakeClock,
    FakeDashboardSummaryRepository,
    FakeTransactionRepository,
    make_summary,
)

pytestmark = pytest.mark.unit


def test_get_dashboard_defaults_to_current_week_and_never_aggregates() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    repository.save(
        make_summary(
            user_id=user_id,
            period=Period.WEEKLY,
            summary_date=date(2025, 1, 13),
            income=Decimal("100.00"),
            expense=Decimal("25.00"),
        )
    )
    transaction_repository = FakeTransactionRepository()

    result = GetUserDashboard(repository, FakeClock()).execute(
        GetUserDashboardCommand(user_id, Period.WEEKLY)
    )

    assert result.start_date == date(2025, 1, 13)
    assert result.end_date == date(2025, 1, 19)
    assert len(result.summaries) == 1
    assert result.summaries[0].net_balance.amount == Decimal("75.00")
    assert not transaction_repository.calls


def test_overview_reads_current_precomputed_snapshots_only() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    repository.save(
        make_summary(
            user_id=user_id,
            period=Period.DAILY,
            summary_date=date(2025, 1, 15),
            income=Decimal("10.00"),
        )
    )
    repository.save(
        make_summary(
            user_id=user_id,
            period=Period.WEEKLY,
            summary_date=date(2025, 1, 13),
            income=Decimal("70.00"),
        )
    )

    result = GetDashboardOverview(repository, FakeClock()).execute(user_id)

    assert result.as_of_date == date(2025, 1, 15)
    assert result.today is not None
    assert result.today.total_income.amount == Decimal("10.00")
    assert result.this_week is not None
    assert result.this_week.total_income.amount == Decimal("70.00")
    assert result.this_month is None


def test_get_dashboard_returns_empty_data_for_missing_precomputation() -> None:
    result = GetUserDashboard(
        FakeDashboardSummaryRepository(),
        FakeClock(),
    ).execute(
        GetUserDashboardCommand(
            uuid4(),
            Period.MONTHLY,
            date(2025, 1, 1),
            date(2025, 1, 31),
        )
    )

    assert result.summaries == ()


def test_get_dashboard_rejects_oversized_range() -> None:
    with pytest.raises(InvalidDashboardQuery, match="cannot exceed"):
        GetUserDashboard(FakeDashboardSummaryRepository(), FakeClock()).execute(
            GetUserDashboardCommand(
                uuid4(),
                Period.DAILY,
                date(2024, 1, 1),
                date(2025, 1, 2),
            )
        )


def test_generate_daily_summary_reads_transaction_aggregates() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    transactions = FakeTransactionRepository(
        _totals(Decimal("500.00"), Decimal("125.50"))
    )

    summary = GenerateDashboardSummary(
        repository,
        transactions,
        FakeClock(),
    ).execute(GenerateDashboardSummaryCommand(user_id, Period.DAILY, date(2025, 1, 10)))

    assert transactions.calls == [(user_id, date(2025, 1, 10), date(2025, 1, 10))]
    assert summary.total_income.amount == Decimal("500.00")
    assert summary.total_expense.amount == Decimal("125.50")
    assert summary.net_balance.amount == Decimal("374.50")
    assert not summary.is_stale


def test_generate_weekly_summary_aggregates_complete_daily_rows() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    for day in range(6, 13):
        repository.save(
            make_summary(
                user_id=user_id,
                period=Period.DAILY,
                summary_date=date(2025, 1, day),
                income=Decimal("10.00"),
                expense=Decimal("2.00"),
            )
        )

    summary = GenerateDashboardSummary(
        repository,
        FakeTransactionRepository(),
        FakeClock(),
    ).execute(GenerateDashboardSummaryCommand(user_id, Period.WEEKLY, date(2025, 1, 8)))

    assert summary.summary_date.value == date(2025, 1, 6)
    assert summary.total_income.amount == Decimal("70.00")
    assert summary.total_expense.amount == Decimal("14.00")
    assert summary.net_balance.amount == Decimal("56.00")
    assert not summary.is_stale


def test_incomplete_weekly_source_produces_stale_snapshot() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    repository.save(
        make_summary(
            user_id=user_id,
            period=Period.DAILY,
            summary_date=date(2025, 1, 10),
            income=Decimal("10.00"),
        )
    )

    summary = GenerateDashboardSummary(
        repository,
        FakeTransactionRepository(),
        FakeClock(),
    ).execute(
        GenerateDashboardSummaryCommand(user_id, Period.WEEKLY, date(2025, 1, 13))
    )

    assert summary.is_stale
    assert summary.stale_at is not None


def test_monthly_summary_uses_weeks_and_corrects_month_boundaries() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    for day, income, expense in (
        (date(2025, 1, 1), Decimal("10.00"), Decimal("1.00")),
        (date(2025, 1, 2), Decimal("20.00"), Decimal("2.00")),
        (date(2025, 1, 3), Decimal("0.00"), Decimal("0.00")),
        (date(2025, 1, 4), Decimal("0.00"), Decimal("0.00")),
        (date(2025, 1, 5), Decimal("0.00"), Decimal("0.00")),
        (date(2025, 1, 31), Decimal("30.00"), Decimal("3.00")),
    ):
        repository.save(
            make_summary(
                user_id=user_id,
                period=Period.DAILY,
                summary_date=day,
                income=income,
                expense=expense,
            )
        )
    for week_start, income, expense in (
        (date(2024, 12, 30), Decimal("100.00"), Decimal("10.00")),
        (date(2025, 1, 6), Decimal("200.00"), Decimal("20.00")),
        (date(2025, 1, 13), Decimal("300.00"), Decimal("30.00")),
        (date(2025, 1, 20), Decimal("400.00"), Decimal("40.00")),
        (date(2025, 1, 27), Decimal("500.00"), Decimal("50.00")),
    ):
        repository.save(
            make_summary(
                user_id=user_id,
                period=Period.WEEKLY,
                summary_date=week_start,
                income=income,
                expense=expense,
            )
        )

    summary = GenerateDashboardSummary(
        repository,
        FakeTransactionRepository(),
        FakeClock(),
    ).execute(
        GenerateDashboardSummaryCommand(user_id, Period.MONTHLY, date(2025, 1, 15))
    )

    assert summary.total_income.amount == Decimal("530.00")
    assert summary.total_expense.amount == Decimal("53.00")
    assert summary.net_balance.amount == Decimal("477.00")
    assert not summary.is_stale


def test_generation_does_not_bypass_immutable_closed_summary() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    use_case = GenerateDashboardSummary(
        repository,
        FakeTransactionRepository(_totals(Decimal("10.00"), Decimal("0.00"))),
        FakeClock(),
    )
    use_case.execute(
        GenerateDashboardSummaryCommand(user_id, Period.DAILY, date(2025, 1, 10))
    )

    with pytest.raises(DashboardSummaryImmutable):
        use_case.execute(
            GenerateDashboardSummaryCommand(user_id, Period.DAILY, date(2025, 1, 10))
        )


def test_invalidation_marks_all_granularities_and_is_idempotent() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    affected_date = date(2025, 1, 15)
    for period in Period:
        repository.save(
            make_summary(
                user_id=user_id,
                period=period,
                summary_date=affected_date,
            )
        )
    use_case = InvalidateUserCache(repository, FakeClock())
    command = InvalidateUserCacheCommand(user_id, (affected_date, affected_date))

    assert use_case.execute(command) == 3
    assert use_case.execute(command) == 0
    assert all(summary.is_stale for summary in repository.summaries.values())


def test_invalidation_can_limit_changes_to_daily_boundary_rows() -> None:
    user_id = uuid4()
    repository = FakeDashboardSummaryRepository()
    for period in Period:
        repository.save(
            make_summary(
                user_id=user_id,
                period=period,
                summary_date=date(2025, 1, 15),
            )
        )

    changed = InvalidateUserCache(repository, FakeClock()).execute(
        InvalidateUserCacheCommand(
            user_id,
            (date(2025, 1, 15),),
            (Period.DAILY,),
        )
    )

    daily = repository.get(
        user_id,
        Period.DAILY,
        SummaryDate(date(2025, 1, 15)),
    )
    weekly = repository.get(
        user_id,
        Period.WEEKLY,
        SummaryDate(date(2025, 1, 13)),
    )

    assert changed == 1
    assert daily is not None and daily.is_stale
    assert weekly is not None and not weekly.is_stale


def _totals(income: Decimal, expense: Decimal) -> PeriodTotals:
    return PeriodTotals(
        income=TotalIncome(income),
        expense=TotalExpense(expense),
        net_balance=NetBalance(income - expense),
    )
