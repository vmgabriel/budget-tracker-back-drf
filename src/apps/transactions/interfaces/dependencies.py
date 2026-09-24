"""Composition of transaction use cases and infrastructure adapters."""

from dataclasses import dataclass

from apps.transactions.application.use_cases import (
    CreateTransaction,
    DeleteTransaction,
    GetTransaction,
    ListUserTransactions,
    UpdateTransaction,
)
from apps.transactions.infrastructure.clock import SystemClock
from apps.transactions.infrastructure.persistence.repositories import (
    DjangoTransactionRepository,
)


@dataclass(frozen=True, slots=True)
class TransactionUseCases:
    """Transaction use cases sharing one persistence adapter."""

    create: CreateTransaction
    get: GetTransaction
    list: ListUserTransactions
    update: UpdateTransaction
    delete: DeleteTransaction


def build_transaction_use_cases() -> TransactionUseCases:
    """Build transaction use cases with infrastructure dependencies."""
    repository = DjangoTransactionRepository()
    clock = SystemClock()
    return TransactionUseCases(
        create=CreateTransaction(repository, clock),
        get=GetTransaction(repository),
        list=ListUserTransactions(repository),
        update=UpdateTransaction(repository, clock),
        delete=DeleteTransaction(repository),
    )
