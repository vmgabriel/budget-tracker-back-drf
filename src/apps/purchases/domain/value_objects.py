"""Immutable value objects for the purchases domain.

Pure Python only: no Django, DRF, Celery, or persistence imports are allowed
here, so the module stays testable without infrastructure.
"""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID

from apps.purchases.domain.exceptions import InvalidArchiveDelay

DEFAULT_ARCHIVE_DELAY = Decimal("7.0")
"""Days a completed list is kept before it is soft-deleted by default."""

MAX_TAG_NAME_LENGTH = 50
MAX_ITEM_NAME_LENGTH = 200
MAX_LIST_NAME_LENGTH = 200
MAX_ITEM_DETAILS_LENGTH = 1000
MAX_ITEM_DESCRIPTION_LENGTH = 2000
MAX_URL_LENGTH = 500
MAX_QUANTITY = 9999
MAX_ESTIMATED_PRICE = Decimal("9999999999.99")
DEFAULT_WISHLIST_NAME = "My Wishlist"


def _require_uuid(value: UUID, label: str) -> None:
    if not isinstance(value, UUID):
        raise TypeError(f"{label} must contain a UUID.")


class ListPriority(StrEnum):
    """Importance assigned to a shopping list."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def label(self) -> str:
        """Return the human-readable priority label."""
        return self.value.capitalize()


LIST_PRIORITY_CHOICES: tuple[tuple[str, str], ...] = (
    (ListPriority.HIGH.value, "High"),
    (ListPriority.MEDIUM.value, "Medium"),
    (ListPriority.LOW.value, "Low"),
)


class WishlistPriority(StrEnum):
    """Desire level assigned to a wishlist item."""

    MUST_HAVE = "must_have"
    WANTED = "wanted"
    NICE_TO_HAVE = "nice_to_have"

    @property
    def label(self) -> str:
        """Return the human-readable priority label."""
        return self.value.replace("_", " ").capitalize()


WISHLIST_PRIORITY_CHOICES: tuple[tuple[str, str], ...] = (
    (WishlistPriority.MUST_HAVE.value, "Must Have"),
    (WishlistPriority.WANTED.value, "Wanted"),
    (WishlistPriority.NICE_TO_HAVE.value, "Nice To Have"),
)


class ItemStatus(StrEnum):
    """Whether a list or an item is still to be bought."""

    PENDING = "pending"
    PURCHASED = "purchased"

    @property
    def label(self) -> str:
        """Return the human-readable status label."""
        return self.value.capitalize()


ITEM_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    (ItemStatus.PENDING.value, "Pending"),
    (ItemStatus.PURCHASED.value, "Purchased"),
)


@dataclass(frozen=True, slots=True)
class ShoppingListId:
    """Identity of a persisted shopping list."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "ShoppingListId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class WishlistId:
    """Identity of a persisted wishlist."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "WishlistId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ShoppingListItemId:
    """Identity of a persisted shopping list item."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "ShoppingListItemId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class WishlistItemId:
    """Identity of a persisted wishlist item."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "WishlistItemId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class TagId:
    """Identity of a persisted tag."""

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "TagId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class UserId:
    """Reference to a user owned by the users context.

    Duplicated intentionally: bounded contexts never import each other's
    models, so each context keeps its own copy of shared identity concepts.
    """

    value: UUID

    def __post_init__(self) -> None:
        _require_uuid(self.value, "UserId")

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ArchiveDelay:
    """How many days a completed list stays active before archival."""

    days: Decimal | int | float = DEFAULT_ARCHIVE_DELAY

    def __post_init__(self) -> None:
        try:
            days = Decimal(str(self.days))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvalidArchiveDelay(
                "Archive delay must be a valid decimal number of days."
            ) from error
        if not days.is_finite():
            raise InvalidArchiveDelay("Archive delay must be finite.")
        if days < 0:
            raise InvalidArchiveDelay("Archive delay cannot be negative.")
        object.__setattr__(self, "days", days)


@dataclass(frozen=True, slots=True)
class Quantity:
    """A strictly positive item quantity."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise TypeError("Quantity must be an integer.")
        if self.value < 1:
            raise ValueError("Quantity must be greater than or equal to one.")
        if self.value > MAX_QUANTITY:
            raise ValueError(f"Quantity must not exceed {MAX_QUANTITY}.")

    def __int__(self) -> int:
        return self.value


@dataclass(frozen=True, slots=True)
class EstimatedPrice:
    """A finite, non-negative estimated price for a wishlist item."""

    amount: Decimal

    def __post_init__(self) -> None:
        try:
            amount = Decimal(str(self.amount))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValueError(
                "Estimated price must be a valid decimal value."
            ) from error
        if not amount.is_finite():
            raise ValueError("Estimated price must be finite.")
        if amount < 0:
            raise ValueError("Estimated price cannot be negative.")
        if amount > MAX_ESTIMATED_PRICE:
            raise ValueError(f"Estimated price must not exceed {MAX_ESTIMATED_PRICE}.")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class Link:
    """An optional http(s) URL attached to a wishlist item."""

    value: str

    def __post_init__(self) -> None:
        normalized = " ".join(self.value.split())
        if not normalized:
            raise ValueError("Link cannot be empty.")
        if len(normalized) > MAX_URL_LENGTH:
            raise ValueError(f"Link cannot exceed {MAX_URL_LENGTH} characters.")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Link must be an http or https URL.")
        if "." not in normalized.split("//", maxsplit=1)[-1].split("/", maxsplit=1)[0]:
            raise ValueError("Link must contain a valid host.")
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
