"""Immutable value objects for the transactions domain."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

CENT = Decimal("0.01")
MAX_MONEY_AMOUNT = Decimal("9999999999.99")


class TransactionType(StrEnum):
    """Financial transaction classifications supported by the application."""

    INCOME = "income"
    EXPENSE = "expense"
    INVESTMENT = "investment"
    SAVINGS = "savings"

    @property
    def label(self) -> str:
        """Return the human-readable type label."""
        return self.value.capitalize()


TRANSACTION_CHOICES: tuple[tuple[str, str], ...] = (
    ("income", "Income"),
    ("expense", "Expense"),
    ("investment", "Investment"),
    ("savings", "Savings"),
)


@dataclass(frozen=True, slots=True)
class TransactionId:
    """Identity of a persisted transaction."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("TransactionId must contain a UUID.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class Money:
    """A finite, strictly positive monetary amount."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError("Amount must be a valid decimal value.") from error
        if not amount.is_finite():
            raise ValueError("Amount must be finite.")
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        if amount > MAX_MONEY_AMOUNT:
            raise ValueError("Amount must not exceed 9999999999.99.")
        if amount != amount.quantize(CENT):
            raise ValueError("Amount must have at most two decimal places.")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class Category:
    """A normalized, non-empty transaction category."""

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split())
        if not normalized:
            raise ValueError("Category cannot be empty.")
        if len(normalized) > 100:
            raise ValueError("Category cannot exceed 100 characters.")
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class TransactionDate:
    """A calendar date on which a transaction occurred."""

    value: date

    def __post_init__(self) -> None:
        if type(self.value) is not date:
            raise ValueError("Transaction date must be a date.")
