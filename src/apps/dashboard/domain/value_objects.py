"""Immutable value objects for pre-computed dashboard summaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CENT = Decimal("0.01")
MAX_DASHBOARD_AMOUNT = Decimal("9999999999999999.99")


class Period(StrEnum):
    """Calendar granularity supported by dashboard summaries."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

    @property
    def label(self) -> str:
        """Return the human-readable period label."""
        return self.value.capitalize()

    def start(self, value: SummaryDate) -> SummaryDate:
        """Normalize a date to the first day represented by this period."""
        if self is Period.DAILY:
            return value
        if self is Period.WEEKLY:
            return SummaryDate(value.value - timedelta(days=value.value.weekday()))
        return SummaryDate(value.value.replace(day=1))

    def end(self, value: SummaryDate) -> SummaryDate:
        """Return the last day represented by a normalized period start."""
        normalized = self.start(value)
        if self is Period.DAILY:
            return normalized
        if self is Period.WEEKLY:
            return SummaryDate(normalized.value + timedelta(days=6))
        if normalized.value.month == 12:
            next_month = normalized.value.replace(
                year=normalized.value.year + 1, month=1
            )
        else:
            next_month = normalized.value.replace(month=normalized.value.month + 1)
        return SummaryDate(next_month - timedelta(days=1))


PERIOD_CHOICES: tuple[tuple[str, str], ...] = tuple(
    (period.value, period.label) for period in Period
)


def is_valid_timezone(timezone_str: str) -> bool:
    """Return whether the string names a valid IANA timezone."""
    if not isinstance(timezone_str, str) or not timezone_str:
        return False
    try:
        ZoneInfo(timezone_str)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return False
    return True


def utc_to_local_date(utc_dt: datetime, timezone_str: str) -> date:
    """Convert a timezone-aware UTC datetime to the user's local calendar date."""
    if utc_dt.tzinfo is None or utc_dt.utcoffset() is None:
        raise ValueError("utc_dt must be timezone-aware.")
    try:
        local = utc_dt.astimezone(ZoneInfo(timezone_str))
    except (ZoneInfoNotFoundError, ValueError, KeyError) as error:
        raise ValueError(f"Unknown timezone: {timezone_str!r}") from error
    return local.date()


def _decimal_amount(value: Decimal) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("Dashboard amounts must be valid decimal values.")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValueError("Dashboard amounts must be valid decimal values.") from error
    if not amount.is_finite():
        raise ValueError("Dashboard amounts must be finite.")
    if abs(amount) > MAX_DASHBOARD_AMOUNT:
        raise ValueError("Dashboard amount is outside the supported range.")
    if amount != amount.quantize(CENT):
        raise ValueError("Dashboard amounts must have at most two decimal places.")
    return amount


def _non_negative_amount(value: Decimal) -> Decimal:
    amount = _decimal_amount(value)
    if amount < 0:
        raise ValueError("Dashboard totals cannot be negative.")
    return amount


@dataclass(frozen=True, slots=True)
class SummaryId:
    """Identity of a persisted dashboard summary."""

    value: UUID

    def __post_init__(self) -> None:
        if not isinstance(self.value, UUID):
            raise TypeError("SummaryId must contain a UUID.")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SummaryDate:
    """A calendar date used as a period anchor in the user's local timezone."""

    value: date

    def __post_init__(self) -> None:
        if not isinstance(self.value, date) or isinstance(self.value, datetime):
            raise ValueError("Summary date must be a date.")


@dataclass(frozen=True, slots=True)
class TotalIncome:
    """Non-negative income included in a dashboard period."""

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _non_negative_amount(self.amount))


@dataclass(frozen=True, slots=True)
class TotalExpense:
    """Non-negative expense included in a dashboard period."""

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _non_negative_amount(self.amount))


@dataclass(frozen=True, slots=True)
class NetBalance:
    """Income less expenses; a deficit is represented by a negative value."""

    amount: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal_amount(self.amount))


@dataclass(frozen=True, slots=True)
class PeriodTotals:
    """Financial totals calculated for one dashboard period."""

    income: TotalIncome
    expense: TotalExpense
    net_balance: NetBalance

    def __post_init__(self) -> None:
        expected_net = self.income.amount - self.expense.amount
        if self.net_balance.amount != expected_net:
            raise ValueError("Net balance must equal income minus expenses.")
