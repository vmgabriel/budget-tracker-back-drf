"""Django ORM adapters for dashboard persistence ports."""

from datetime import date, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce

from apps.dashboard.application.ports.repositories import (
    DashboardSummaryRepository,
    TransactionRepository,
)
from apps.dashboard.domain.entities import DashboardSummary
from apps.dashboard.domain.value_objects import (
    NetBalance,
    Period,
    PeriodTotals,
    SummaryDate,
    SummaryId,
    TotalExpense,
    TotalIncome,
)
from apps.dashboard.infrastructure.persistence.models import (
    DashboardSummary as DashboardSummaryModel,
)
from apps.transactions.domain.value_objects import TransactionType
from apps.transactions.infrastructure.persistence.models import Transaction


class DjangoDashboardSummaryRepository(DashboardSummaryRepository):
    """Persist and query dashboard snapshots with the Django ORM."""

    def get(
        self,
        user_id: UUID,
        period: Period,
        summary_date: SummaryDate,
    ) -> DashboardSummary | None:
        model = DashboardSummaryModel.objects.filter(
            user_id=user_id,
            period=period.value,
            date=summary_date.value,
        ).first()
        return self._to_domain(model) if model is not None else None

    def list_for_user(
        self,
        user_id: UUID,
        period: Period,
        start_date: date,
        end_date: date,
    ) -> list[DashboardSummary]:
        if end_date < start_date:
            return []
        models = DashboardSummaryModel.objects.filter(
            user_id=user_id,
            period=period.value,
            date__range=(start_date, end_date),
        ).order_by("date")
        return [self._to_domain(model) for model in models]

    def save(self, summary: DashboardSummary) -> DashboardSummary:
        model, _ = DashboardSummaryModel.objects.update_or_create(
            user_id=summary.user_id,
            period=summary.period.value,
            date=summary.summary_date.value,
            defaults={
                "total_income": summary.total_income.amount,
                "total_expense": summary.total_expense.amount,
                "net_balance": summary.net_balance.amount,
                "is_stale": summary.is_stale,
                "generated_at": summary.generated_at,
                "stale_at": summary.stale_at,
            },
        )
        return self._to_domain(model)

    def mark_stale(
        self,
        user_id: UUID,
        periods: set[tuple[Period, SummaryDate]],
        stale_at: datetime,
    ) -> int:
        if not periods:
            return 0
        query = Q()
        for period, summary_date in periods:
            query |= Q(period=period.value, date=summary_date.value)
        return DashboardSummaryModel.objects.filter(
            query,
            user_id=user_id,
            is_stale=False,
        ).update(is_stale=True, stale_at=stale_at, updated_at=stale_at)

    @staticmethod
    def _to_domain(model: DashboardSummaryModel) -> DashboardSummary:
        return DashboardSummary.create(
            user_id=model.user_id,
            period=Period(model.period),
            summary_date=SummaryDate(model.date),
            totals=PeriodTotals(
                income=TotalIncome(model.total_income),
                expense=TotalExpense(model.total_expense),
                net_balance=NetBalance(model.net_balance),
            ),
            generated_at=model.generated_at,
            is_stale=model.is_stale,
            stale_at=model.stale_at,
            id=SummaryId(model.id),
        )


class DjangoTransactionReadRepository(TransactionRepository):
    """Aggregate transaction values without exposing mutable persistence APIs."""

    def aggregate_totals(
        self,
        user_id: UUID,
        start_date: date,
        end_date: date,
    ) -> PeriodTotals:
        if end_date < start_date:
            return _zero_totals()
        amount_output: DecimalField = DecimalField(max_digits=18, decimal_places=2)
        result = Transaction.objects.filter(
            user_id=user_id,
            date__range=(start_date, end_date),
        ).aggregate(
            total_income=Coalesce(
                Sum(
                    "amount",
                    filter=Q(transaction_type=TransactionType.INCOME.value),
                ),
                Value(Decimal("0.00")),
                output_field=amount_output,
            ),
            total_expense=Coalesce(
                Sum(
                    "amount",
                    filter=Q(transaction_type=TransactionType.EXPENSE.value),
                ),
                Value(Decimal("0.00")),
                output_field=amount_output,
            ),
        )
        totals = cast(dict[str, Decimal], result)
        return PeriodTotals(
            income=TotalIncome(totals["total_income"]),
            expense=TotalExpense(totals["total_expense"]),
            net_balance=NetBalance(totals["total_income"] - totals["total_expense"]),
        )


def _zero_totals() -> PeriodTotals:
    return PeriodTotals(
        income=TotalIncome(Decimal("0.00")),
        expense=TotalExpense(Decimal("0.00")),
        net_balance=NetBalance(Decimal("0.00")),
    )
