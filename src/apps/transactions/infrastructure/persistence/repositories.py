"""Django ORM implementations of the transaction-context repository ports."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction as db_transaction
from django.db.models import DecimalField, Q, QuerySet, Sum, Value
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek

from apps.transactions.application.analytics import (
    GROUP_BY_CATEGORY,
    PERIOD_DAILY,
    PERIOD_MONTHLY,
    PERIOD_WEEKLY,
    TRANSACTION_TYPE_ORDER,
    AnalyticsAggregate,
    CategoryTotal,
    TypeBucketTotals,
)
from apps.transactions.application.ports.repositories import (
    AccountRepository,
    TransactionRepository,
)
from apps.transactions.domain.entities import Account, Transaction
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import (
    AccountId,
    AccountType,
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)
from apps.transactions.infrastructure.persistence.models import (
    Account as AccountModel,
)
from apps.transactions.infrastructure.persistence.models import (
    Transaction as TransactionModel,
)


class DjangoAccountRepository(AccountRepository):
    """Persist and retrieve funding accounts with the Django ORM."""

    def add(self, account: Account) -> Account:
        model = AccountModel(
            id=account.id.value if account.id is not None else None,
            user_id=account.user_id,
            name=account.name,
            account_type=account.account_type.value,
            is_active=account.is_active,
        )
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def get_by_id_for_user(
        self, account_id: AccountId, user_id: UUID
    ) -> Account | None:
        model = AccountModel.objects.filter(
            pk=account_id.value,
            user_id=user_id,
        ).first()
        return self._to_domain(model) if model is not None else None

    def list_active_by_user(self, user_id: UUID) -> list[Account]:
        models = AccountModel.objects.filter(user_id=user_id, is_active=True).order_by(
            "name", "id"
        )
        return [self._to_domain(model) for model in models]

    @staticmethod
    def _to_domain(model: AccountModel) -> Account:
        return Account(
            id=AccountId(model.id),
            user_id=model.user_id,
            name=model.name,
            account_type=AccountType(model.account_type),
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DjangoTransactionRepository(TransactionRepository):
    """Persist and retrieve transaction aggregates with the Django ORM."""

    def add(self, transaction: Transaction) -> Transaction:
        model = self._to_model(transaction)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._reload(model)

    def get_by_id_for_user(
        self, transaction_id: TransactionId, user_id: UUID
    ) -> Transaction | None:
        model = (
            TransactionModel.objects.select_related("account")
            .filter(
                pk=transaction_id.value,
                user_id=user_id,
            )
            .first()
        )
        return self._to_domain(model) if model is not None else None

    def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            raise ValueError("A persisted transaction must have an identity.")
        model = TransactionModel.objects.filter(
            pk=transaction.id.value,
            user_id=transaction.user_id,
        ).first()
        if model is None:
            raise TransactionNotFound("Transaction not found.")
        model.account_id = (
            transaction.account_id.value if transaction.account_id is not None else None
        )
        model.amount = transaction.amount.amount
        model.transaction_type = transaction.transaction_type.value
        model.category = transaction.category.value
        model.date = transaction.date.value
        model.description = transaction.description or ""
        with db_transaction.atomic():
            model.save(
                update_fields=(
                    "account",
                    "amount",
                    "transaction_type",
                    "category",
                    "date",
                    "description",
                    "updated_at",
                )
            )
        return self._reload(model)

    def delete(self, transaction: Transaction) -> None:
        if transaction.id is None:
            raise ValueError("A persisted transaction must have an identity.")
        deleted, _ = TransactionModel.objects.filter(
            pk=transaction.id.value,
            user_id=transaction.user_id,
        ).delete()
        if not deleted:
            raise TransactionNotFound("Transaction not found.")

    def list_by_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Transaction], int]:
        queryset = TransactionModel.objects.filter(user_id=user_id)
        total = queryset.count()
        models = list(
            queryset.select_related("account").order_by("-date", "-created_at", "-id")[
                offset : offset + limit
            ]
        )
        return [self._to_domain(model) for model in models], total

    def get_analytics_aggregates(
        self,
        user_id: UUID,
        *,
        start_date: date,
        end_date: date,
        group_by: str,
        period: str,
    ) -> list[AnalyticsAggregate]:
        """Aggregate one bounded, owner-scoped range into chart rows.

        Both branches filter on ``user`` and ``date`` so PostgreSQL can use
        ``transaction_owner_date_idx``; the type grouping computes the four
        series in a single pass with conditional sums.
        """
        queryset = TransactionModel.objects.filter(
            user_id=user_id,
            date__gte=start_date,
            date__lte=end_date,
        )
        if group_by == GROUP_BY_CATEGORY:
            return self._category_aggregates(queryset)
        return self._type_aggregates(queryset, period)

    @staticmethod
    def _category_aggregates(
        queryset: QuerySet[TransactionModel],
    ) -> list[AnalyticsAggregate]:
        """Return one total per expense category, largest slice first."""
        rows = (
            queryset.filter(transaction_type=TransactionType.EXPENSE.value)
            .values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total", "category")
        )
        return [
            CategoryTotal(category=row["category"], total=row["total"]) for row in rows
        ]

    @staticmethod
    def _type_aggregates(
        queryset: QuerySet[TransactionModel], period: str
    ) -> list[AnalyticsAggregate]:
        """Return one row per truncated period with the four type totals."""
        trunc = {
            PERIOD_DAILY: TruncDay,
            PERIOD_WEEKLY: TruncWeek,
            PERIOD_MONTHLY: TruncMonth,
        }[period]
        amount_field: DecimalField = DecimalField(max_digits=18, decimal_places=2)
        rows = (
            queryset.annotate(bucket=trunc("date"))
            .values("bucket")
            .annotate(
                **{
                    transaction_type.value: Coalesce(
                        Sum(
                            "amount",
                            filter=Q(transaction_type=transaction_type.value),
                        ),
                        Value(Decimal("0.00")),
                        output_field=amount_field,
                    )
                    for transaction_type in TRANSACTION_TYPE_ORDER
                }
            )
            .order_by("bucket")
        )
        return [
            TypeBucketTotals(
                bucket=_bucket_date(row["bucket"]),
                totals={
                    transaction_type: row[transaction_type.value]
                    for transaction_type in TRANSACTION_TYPE_ORDER
                },
            )
            for row in rows
        ]

    @staticmethod
    def _to_model(transaction: Transaction) -> TransactionModel:
        return TransactionModel(
            id=transaction.id.value if transaction.id is not None else None,
            user_id=transaction.user_id,
            account_id=(
                transaction.account_id.value
                if transaction.account_id is not None
                else None
            ),
            amount=transaction.amount.amount,
            transaction_type=transaction.transaction_type.value,
            category=transaction.category.value,
            date=transaction.date.value,
            description=transaction.description or "",
        )

    def _reload(self, model: TransactionModel) -> Transaction:
        """Re-read a written row so the hydrated account name is accurate."""
        if model.account_id is None:
            return self._to_domain(model)
        stored = TransactionModel.objects.select_related("account").get(pk=model.pk)
        return self._to_domain(stored)

    @staticmethod
    def _to_domain(model: TransactionModel) -> Transaction:
        account_name: str | None = None
        if model.account_id is not None:
            account = model.account
            if account is not None:
                account_name = account.name
        return Transaction(
            id=TransactionId(model.id),
            user_id=model.user_id,
            amount=Money(model.amount),
            transaction_type=TransactionType(model.transaction_type),
            category=Category(model.category),
            date=TransactionDate(model.date),
            description=model.description or None,
            created_at=model.created_at,
            updated_at=model.updated_at,
            account_id=(
                AccountId(model.account_id) if model.account_id is not None else None
            ),
            account_name=account_name,
        )


def _bucket_date(value: date | datetime) -> date:
    """Normalize a truncated annotation, which may arrive as a datetime."""
    return value.date() if isinstance(value, datetime) else value
