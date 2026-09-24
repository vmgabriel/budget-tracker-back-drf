"""In-memory test doubles for transaction application ports."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from apps.transactions.domain.entities import Transaction
from apps.transactions.domain.value_objects import (
    Category,
    Money,
    TransactionDate,
    TransactionId,
    TransactionType,
)

FIXED_NOW = datetime(2025, 1, 15, 12, tzinfo=UTC)


class FakeTransactionRepository:
    """Store transaction aggregates in memory for application tests."""

    def __init__(self) -> None:
        self.transactions: dict[TransactionId, Transaction] = {}

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


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


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
    )
    transaction.id = TransactionId(transaction_id or uuid4())
    return transaction
