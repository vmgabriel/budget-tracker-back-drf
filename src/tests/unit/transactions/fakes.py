"""In-memory test doubles for transaction application ports."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from apps.transactions.application.analytics import AnalyticsAggregate
from apps.transactions.domain.entities import Account, Transaction
from apps.transactions.domain.value_objects import (
    AccountId,
    AccountType,
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)

FIXED_NOW = datetime(2025, 1, 15, 12, tzinfo=UTC)


class FakeTransactionRepository:
    """Store transaction aggregates in memory for application tests."""

    def __init__(self, analytics: list[AnalyticsAggregate] | None = None) -> None:
        self.transactions: dict[TransactionId, Transaction] = {}
        self.analytics = list(analytics or [])
        self.analytics_calls: list[dict[str, object]] = []

    def add(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            transaction.id = TransactionId(uuid4())
        self.transactions[transaction.id] = transaction
        return transaction

    def get_by_id_for_user(
        self, transaction_id: TransactionId, user_id: UUID
    ) -> Transaction | None:
        transaction = self.transactions.get(transaction_id)
        if transaction is None or transaction.user_id != user_id:
            return None
        return transaction

    def update(self, transaction: Transaction) -> Transaction:
        if transaction.id is None:
            raise ValueError("Cannot update an unidentified transaction.")
        self.transactions[transaction.id] = transaction
        return transaction

    def delete(self, transaction: Transaction) -> None:
        if transaction.id is None:
            raise ValueError("Cannot delete an unidentified transaction.")
        del self.transactions[transaction.id]

    def list_by_user(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Transaction], int]:
        owned = [
            transaction
            for transaction in self.transactions.values()
            if transaction.user_id == user_id
        ]
        owned.sort(
            key=lambda item: (
                item.date.value,
                item.created_at,
                str(item.id),
            ),
            reverse=True,
        )
        return owned[offset : offset + limit], len(owned)

    def get_analytics_aggregates(
        self,
        user_id: UUID,
        *,
        start_date: date,
        end_date: date,
        group_by: str,
        period: str,
    ) -> list[AnalyticsAggregate]:
        self.analytics_calls.append(
            {
                "user_id": user_id,
                "start_date": start_date,
                "end_date": end_date,
                "group_by": group_by,
                "period": period,
            }
        )
        return list(self.analytics)


class FakeAccountRepository:
    """Store funding accounts in memory for application tests."""

    def __init__(self) -> None:
        self.accounts: dict[AccountId, Account] = {}

    def add(self, account: Account) -> Account:
        if account.id is None:
            account.id = AccountId(uuid4())
        self.accounts[account.id] = account
        return account

    def get_by_id_for_user(
        self, account_id: AccountId, user_id: UUID
    ) -> Account | None:
        account = self.accounts.get(account_id)
        if account is None or account.user_id != user_id:
            return None
        return account

    def list_active_by_user(self, user_id: UUID) -> list[Account]:
        active = [
            account
            for account in self.accounts.values()
            if account.user_id == user_id and account.is_active
        ]
        active.sort(key=lambda item: (item.name, str(item.id)))
        return active


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


def make_account(
    *,
    account_id: UUID | None = None,
    user_id: UUID | None = None,
    name: str = "Main Card",
    account_type: AccountType = AccountType.CREDIT_CARD,
    is_active: bool = True,
    now: datetime = FIXED_NOW,
) -> Account:
    """Build a persisted funding account for use-case tests."""
    account = Account.create(
        user_id=user_id or uuid4(),
        name=name,
        account_type=account_type,
        now=now,
    )
    account.id = AccountId(account_id or uuid4())
    account.is_active = is_active
    return account


def make_transaction(
    *,
    transaction_id: UUID | None = None,
    user_id: UUID | None = None,
    amount: Decimal = Decimal("25.00"),
    transaction_type: TransactionType = TransactionType.EXPENSE,
    category: str = "Food",
    transaction_date: date = date(2025, 1, 10),
    description: str | None = "Lunch",
    now: datetime = FIXED_NOW,
    account_id: AccountId | None = None,
    account_name: str | None = None,
) -> Transaction:
    """Build a persisted transaction for use-case tests."""
    transaction = Transaction.create(
        user_id=user_id or uuid4(),
        amount=Money(amount),
        transaction_type=transaction_type,
        category=Category(category),
        date=TransactionDate(transaction_date),
        description=description,
        now=now,
        account_id=account_id,
    )
    transaction.id = TransactionId(transaction_id or uuid4())
    transaction.account_name = account_name
    return transaction
