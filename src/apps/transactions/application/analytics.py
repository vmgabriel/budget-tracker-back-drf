"""Analytics vocabulary and read models shared by the use case and its adapter.

The strings here are the wire contract of ``GET /api/v1/transactions/analytics/``
and the keys the ORM adapter expects, so they live in one place instead of being
restated in every layer.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.transactions.domain.value_objects import TransactionType

GROUP_BY_TYPE = "type"
GROUP_BY_CATEGORY = "category"
GROUP_BY_CHOICES: tuple[str, ...] = (GROUP_BY_TYPE, GROUP_BY_CATEGORY)

PERIOD_DAILY = "daily"
PERIOD_WEEKLY = "weekly"
PERIOD_MONTHLY = "monthly"
PERIOD_CHOICES: tuple[str, ...] = (PERIOD_DAILY, PERIOD_WEEKLY, PERIOD_MONTHLY)
DEFAULT_PERIOD = PERIOD_MONTHLY

# Inclusive bound on ``end_date - start_date``: one year plus the leap day.
MAX_RANGE_DAYS = 366

TRANSACTION_TYPE_ORDER: tuple[TransactionType, ...] = (
    TransactionType.INCOME,
    TransactionType.EXPENSE,
    TransactionType.INVESTMENT,
    TransactionType.SAVINGS,
)


@dataclass(frozen=True, slots=True)
class TypeBucketTotals:
    """Sums per transaction type for one truncated period start."""

    bucket: date
    totals: Mapping[TransactionType, Decimal]


@dataclass(frozen=True, slots=True)
class CategoryTotal:
    """Expense total for one category."""

    category: str
    total: Decimal


# ``group_by="type"`` yields TypeBucketTotals, ``group_by="category"`` yields
# CategoryTotal. The use case knows which one it asked for.
AnalyticsAggregate = TypeBucketTotals | CategoryTotal
