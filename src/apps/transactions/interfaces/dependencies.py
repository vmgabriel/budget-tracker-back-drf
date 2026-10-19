"""Composition of transaction use cases and infrastructure adapters."""

from dataclasses import dataclass

from apps.transactions.application.use_cases import (
    CreateAccount,
    CreateTransaction,
    DeleteTransaction,
    GetAccount,
    GetTransaction,
    ListUserAccounts,
    ListUserTransactions,
    UpdateTransaction,
    UpdateTransactionAccount,
)
from apps.transactions.infrastructure.persistence.repositories import (
    DjangoAccountRepository,
    DjangoTransactionRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class TransactionUseCases:
    """Transaction use cases sharing one persistence adapter."""

    create: CreateTransaction
    get: GetTransaction
    list: ListUserTransactions
    update: UpdateTransaction
    delete: DeleteTransaction
    update_account: UpdateTransactionAccount


@dataclass(frozen=True, slots=True)
class AccountUseCases:
    """Funding-account use cases sharing one persistence adapter."""

    create: CreateAccount
    get: GetAccount
    list: ListUserAccounts


def build_transaction_use_cases() -> TransactionUseCases:
    """Build transaction use cases with infrastructure dependencies."""
    repository = DjangoTransactionRepository()
    accounts = DjangoAccountRepository()
    clock = SystemClock()
    return TransactionUseCases(
        create=CreateTransaction(repository, clock, accounts),
        get=GetTransaction(repository),
        list=ListUserTransactions(repository),
        update=UpdateTransaction(repository, clock, accounts),
        delete=DeleteTransaction(repository),
        update_account=UpdateTransactionAccount(repository, accounts, clock),
    )


def build_account_use_cases() -> AccountUseCases:
    """Build funding-account use cases with infrastructure dependencies."""
    accounts = DjangoAccountRepository()
    clock = SystemClock()
    return AccountUseCases(
        create=CreateAccount(accounts, clock),
        get=GetAccount(accounts),
        list=ListUserAccounts(accounts),
    )
