"""Django ORM implementation of the transaction repository port."""

from uuid import UUID

from django.db import transaction as db_transaction

from apps.transactions.application.ports.repositories import TransactionRepository
from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.exceptions import TransactionNotFound
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)
from apps.transactions.infrastructure.persistence.models import (
    Transaction as TransactionModel,
)


class DjangoTransactionRepository(TransactionRepository):
    """Persist and retrieve transaction aggregates with the Django ORM."""

    def add(self, transaction: Transaction) -> Transaction:
        model = self._to_model(transaction)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def get_by_id_for_user(
        self, transaction_id: TransactionId, user_id: UUID
    ) -> Transaction | None:
        model = TransactionModel.objects.filter(
            pk=transaction_id.value,
            user_id=user_id,
        ).first()
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
        model.amount = transaction.amount.amount
        model.transaction_type = transaction.transaction_type.value
        model.category = transaction.category.value
        model.date = transaction.date.value
        model.description = transaction.description or ""
        with db_transaction.atomic():
            model.save(
                update_fields=(
                    "amount",
                    "transaction_type",
                    "category",
                    "date",
                    "description",
                    "updated_at",
                )
            )
        return self._to_domain(model)

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
            queryset.order_by("-date", "-created_at", "-id")[offset : offset + limit]
        )
        return [self._to_domain(model) for model in models], total

    @staticmethod
    def _to_model(transaction: Transaction) -> TransactionModel:
        return TransactionModel(
            id=transaction.id.value if transaction.id is not None else None,
            user_id=transaction.user_id,
            amount=transaction.amount.amount,
            transaction_type=transaction.transaction_type.value,
            category=transaction.category.value,
            date=transaction.date.value,
            description=transaction.description or "",
        )

    @staticmethod
    def _to_domain(model: TransactionModel) -> Transaction:
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
        )
