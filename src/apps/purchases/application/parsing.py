"""Translation of primitive command fields into domain value objects.

Interfaces deliver strings and numbers straight from JSON; this module is the
single place where they become enums and value objects, so the ``try``/``except``
that turns a domain failure into ``InvalidPurchasesInput`` is written once per
conversion instead of once per use case.
"""

from decimal import Decimal, InvalidOperation
from enum import StrEnum

from apps.purchases.application.config import PURCHASES_DEFAULTS
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.domain.exceptions import InvalidArchiveDelay
from apps.purchases.domain.value_objects import (
    ArchiveDelay,
    EstimatedPrice,
    ItemStatus,
    Link,
    ListPriority,
    Quantity,
    WishlistPriority,
)


def parse_enum[E: StrEnum](enum_type: type[E], raw: object, label: str) -> E:
    """Convert a raw string into ``enum_type`` or fail with a readable message."""
    if isinstance(raw, enum_type):
        return raw
    try:
        return enum_type(str(raw).strip().lower())
    except ValueError as error:
        allowed = ", ".join(member.value for member in enum_type)
        raise InvalidPurchasesInput(f"{label} must be one of: {allowed}.") from error


def parse_quantity(raw: object) -> Quantity:
    """Convert a raw value into a positive ``Quantity``."""
    if isinstance(raw, bool):
        raise InvalidPurchasesInput("Quantity must be an integer.")
    if isinstance(raw, str):
        try:
            raw = int(raw.strip())
        except ValueError as error:
            raise InvalidPurchasesInput("Quantity must be an integer.") from error
    if isinstance(raw, Decimal):
        raw = int(raw) if raw == raw.to_integral_value() else raw
    if not isinstance(raw, int):
        raise InvalidPurchasesInput("Quantity must be an integer.")
    try:
        return Quantity(raw)
    except (TypeError, ValueError) as error:
        raise InvalidPurchasesInput(str(error)) from error


def parse_estimated_price(raw: object) -> EstimatedPrice:
    """Convert a raw value into a non-negative ``EstimatedPrice``."""
    if isinstance(raw, EstimatedPrice):
        return raw
    try:
        return EstimatedPrice(Decimal(str(raw)))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise InvalidPurchasesInput(str(error)) from error


def parse_link(raw: object, label: str) -> Link:
    """Convert a raw value into an http(s) ``Link``."""
    if isinstance(raw, Link):
        return raw
    try:
        return Link(str(raw))
    except (TypeError, ValueError) as error:
        raise InvalidPurchasesInput(f"{label}: {error}") from error


def parse_list_priority(raw: object) -> ListPriority:
    """Convert a raw value into a ``ListPriority``."""
    return parse_enum(ListPriority, raw, "Priority")


def parse_wishlist_priority(raw: object) -> WishlistPriority:
    """Convert a raw value into a ``WishlistPriority``."""
    return parse_enum(WishlistPriority, raw, "Priority")


def parse_item_status(raw: object) -> ItemStatus:
    """Convert a raw value into an ``ItemStatus``."""
    return parse_enum(ItemStatus, raw, "Status")


def parse_archive_delay(days: Decimal | int | float | None) -> ArchiveDelay:
    """Convert a configured number of days into an ``ArchiveDelay``."""
    if days is None:
        days = PURCHASES_DEFAULTS["ARCHIVE_DELAY_DAYS"]
    try:
        return ArchiveDelay(days)
    except (InvalidArchiveDelay, TypeError, ValueError) as error:
        raise InvalidPurchasesInput(str(error)) from error
