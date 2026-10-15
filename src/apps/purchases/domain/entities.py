"""Purchases aggregates and entities with their business rules.

A shopping list is the aggregate root for its items; a wishlist is the
aggregate root for its items. Tags live in a shared catalogue and are only
ever associated with, or removed from, an item.

Pure Python only: no Django, DRF, Celery, or persistence imports are allowed
here, so the module stays testable without infrastructure.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.purchases.domain.exceptions import (
    InvalidArchiveDelay,
    ShoppingListItemNotFound,
    WishlistItemNotFound,
)
from apps.purchases.domain.value_objects import (
    DEFAULT_ARCHIVE_DELAY,
    DEFAULT_WISHLIST_NAME,
    MAX_ITEM_DESCRIPTION_LENGTH,
    MAX_ITEM_DETAILS_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_LIST_NAME_LENGTH,
    MAX_TAG_NAME_LENGTH,
    ArchiveDelay,
    EstimatedPrice,
    ItemStatus,
    Link,
    ListPriority,
    Quantity,
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    UserId,
    WishlistId,
    WishlistItemId,
    WishlistPriority,
)


def _require_aware(now: datetime, label: str) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(f"{label} timestamps must be timezone-aware.")


def _normalize_name(value: str, *, limit: int, label: str) -> str:
    normalized = " ".join(str(value).split())
    if not normalized:
        raise ValueError(f"{label} cannot be empty.")
    if len(normalized) > limit:
        raise ValueError(f"{label} cannot exceed {limit} characters.")
    return normalized


def _normalize_optional_text(
    value: str | None, *, limit: int, label: str
) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip() or None
    if normalized is not None and len(normalized) > limit:
        raise ValueError(f"{label} cannot exceed {limit} characters.")
    return normalized


def _slugify(value: str) -> str:
    """Build a URL-safe slug from an arbitrary tag name.

    Implemented locally because ``django.utils.text.slugify`` would break the
    purity of the domain layer.
    """
    slug: list[str] = []
    previous_was_separator = False
    for character in str(value).strip().lower():
        if character.isalnum():
            slug.append(character)
            previous_was_separator = False
        elif not previous_was_separator:
            slug.append("-")
            previous_was_separator = True
    return "".join(slug).strip("-")


@dataclass(eq=False, slots=True)
class Tag:
    """A label from the tag catalogue, shared across items."""

    name: str
    slug: str
    id: TagId | None = None

    @classmethod
    def create(cls, *, name: str) -> "Tag":
        """Create a tag, deriving its slug from the normalized name."""
        normalized = _normalize_name(name, limit=MAX_TAG_NAME_LENGTH, label="Tag name")
        slug = _slugify(normalized)
        if not slug:
            raise ValueError(
                "Tag name must contain at least one alphanumeric character."
            )
        return cls(id=None, name=normalized, slug=slug)

    def rename(self, name: str) -> None:
        """Rename the tag and regenerate its slug."""
        normalized = _normalize_name(name, limit=MAX_TAG_NAME_LENGTH, label="Tag name")
        slug = _slugify(normalized)
        if not slug:
            raise ValueError(
                "Tag name must contain at least one alphanumeric character."
            )
        self.name = normalized
        self.slug = slug

    def matches(self, name: str) -> bool:
        """Return whether ``name`` refers to this tag by name or by slug."""
        candidate = " ".join(str(name).split())
        return candidate == self.name or _slugify(candidate) == self.slug


@dataclass(eq=False, slots=True)
class ShoppingListItem:
    """One thing to buy, belonging to exactly one shopping list."""

    shopping_list_id: ShoppingListId
    name: str
    quantity: Quantity
    id: ShoppingListItemId | None = None
    details: str | None = None
    status: ItemStatus = ItemStatus.PENDING
    tags: list[Tag] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        shopping_list_id: ShoppingListId,
        name: str,
        quantity: Quantity,
        details: str | None = None,
        status: ItemStatus = ItemStatus.PENDING,
        tags: list[Tag] | None = None,
    ) -> "ShoppingListItem":
        """Create an item after validating its invariants."""
        if not isinstance(shopping_list_id, ShoppingListId):
            raise TypeError("Item shopping list must be a ShoppingListId.")
        if not isinstance(quantity, Quantity):
            raise TypeError("Item quantity must be a Quantity.")
        if not isinstance(status, ItemStatus):
            raise ValueError("Item status is invalid.")
        return cls(
            id=None,
            shopping_list_id=shopping_list_id,
            name=_normalize_name(name, limit=MAX_ITEM_NAME_LENGTH, label="Item name"),
            quantity=quantity,
            details=_normalize_optional_text(
                details, limit=MAX_ITEM_DETAILS_LENGTH, label="Item details"
            ),
            status=status,
            tags=list(tags) if tags else [],
        )

    def update(
        self,
        *,
        name: str | None = None,
        quantity: Quantity | None = None,
        details: str | None = None,
        status: ItemStatus | None = None,
    ) -> None:
        """Apply a partial, validated replacement to the item."""
        if quantity is not None and not isinstance(quantity, Quantity):
            raise TypeError("Item quantity must be a Quantity.")
        if status is not None and not isinstance(status, ItemStatus):
            raise ValueError("Item status is invalid.")
        if name is not None:
            self.name = _normalize_name(
                name, limit=MAX_ITEM_NAME_LENGTH, label="Item name"
            )
        if quantity is not None:
            self.quantity = quantity
        if details is not None:
            self.details = _normalize_optional_text(
                details, limit=MAX_ITEM_DETAILS_LENGTH, label="Item details"
            )
        if status is not None:
            self.status = status

    def mark_as_purchased(self) -> None:
        """Flag the item as already bought."""
        self.status = ItemStatus.PURCHASED

    def mark_as_pending(self) -> None:
        """Return the item to the pending state."""
        self.status = ItemStatus.PENDING

    def add_tags(self, tags: list[Tag]) -> int:
        """Associate tags with the item; already attached tags are skipped.

        Returns the number of newly associated tags.
        """
        added = 0
        for tag in tags:
            if any(existing.matches(tag.name) for existing in self.tags):
                continue
            self.tags.append(tag)
            added += 1
        return added

    def remove_tags(self, tags: list[Tag]) -> int:
        """Detach tags from the item; unknown tags are ignored.

        Returns the number of tags actually removed.
        """
        removed = 0
        for tag in tags:
            for index, existing in enumerate(self.tags):
                if existing.matches(tag.name):
                    del self.tags[index]
                    removed += 1
                    break
        return removed


@dataclass(eq=False, slots=True)
class WishlistItem:
    """One wanted product, belonging to exactly one wishlist."""

    wishlist_id: WishlistId
    name: str
    id: WishlistItemId | None = None
    link: Link | None = None
    image_link: Link | None = None
    description: str | None = None
    estimated_price: EstimatedPrice | None = None
    priority: WishlistPriority = WishlistPriority.WANTED
    status: ItemStatus = ItemStatus.PENDING
    tags: list[Tag] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        wishlist_id: WishlistId,
        name: str,
        link: Link | None = None,
        image_link: Link | None = None,
        description: str | None = None,
        estimated_price: EstimatedPrice | None = None,
        priority: WishlistPriority = WishlistPriority.WANTED,
        status: ItemStatus = ItemStatus.PENDING,
        tags: list[Tag] | None = None,
    ) -> "WishlistItem":
        """Create a wishlist item after validating its invariants."""
        if not isinstance(wishlist_id, WishlistId):
            raise TypeError("Item wishlist must be a WishlistId.")
        if link is not None and not isinstance(link, Link):
            raise TypeError("Item link must be a Link.")
        if image_link is not None and not isinstance(image_link, Link):
            raise TypeError("Item image link must be a Link.")
        if estimated_price is not None and not isinstance(
            estimated_price, EstimatedPrice
        ):
            raise TypeError("Item estimated price must be an EstimatedPrice.")
        if not isinstance(priority, WishlistPriority):
            raise ValueError("Item priority is invalid.")
        if not isinstance(status, ItemStatus):
            raise ValueError("Item status is invalid.")
        return cls(
            id=None,
            wishlist_id=wishlist_id,
            name=_normalize_name(name, limit=MAX_ITEM_NAME_LENGTH, label="Item name"),
            link=link,
            image_link=image_link,
            description=_normalize_optional_text(
                description,
                limit=MAX_ITEM_DESCRIPTION_LENGTH,
                label="Item description",
            ),
            estimated_price=estimated_price,
            priority=priority,
            status=status,
            tags=list(tags) if tags else [],
        )

    def update(
        self,
        *,
        name: str | None = None,
        link: Link | None = None,
        image_link: Link | None = None,
        description: str | None = None,
        estimated_price: EstimatedPrice | None = None,
        priority: WishlistPriority | None = None,
        status: ItemStatus | None = None,
    ) -> None:
        """Apply a partial, validated replacement to the item."""
        if link is not None and not isinstance(link, Link):
            raise TypeError("Item link must be a Link.")
        if image_link is not None and not isinstance(image_link, Link):
            raise TypeError("Item image link must be a Link.")
        if estimated_price is not None and not isinstance(
            estimated_price, EstimatedPrice
        ):
            raise TypeError("Item estimated price must be an EstimatedPrice.")
        if priority is not None and not isinstance(priority, WishlistPriority):
            raise ValueError("Item priority is invalid.")
        if status is not None and not isinstance(status, ItemStatus):
            raise ValueError("Item status is invalid.")
        if name is not None:
            self.name = _normalize_name(
                name, limit=MAX_ITEM_NAME_LENGTH, label="Item name"
            )
        if link is not None:
            self.link = link
        if image_link is not None:
            self.image_link = image_link
        if description is not None:
            self.description = _normalize_optional_text(
                description,
                limit=MAX_ITEM_DESCRIPTION_LENGTH,
                label="Item description",
            )
        if estimated_price is not None:
            self.estimated_price = estimated_price
        if priority is not None:
            self.priority = priority
        if status is not None:
            self.status = status

    def mark_as_purchased(self) -> None:
        """Flag the wanted product as already bought."""
        self.status = ItemStatus.PURCHASED

    def mark_as_pending(self) -> None:
        """Return the item to the pending state."""
        self.status = ItemStatus.PENDING

    def add_tags(self, tags: list[Tag]) -> int:
        """Associate tags with the item; already attached tags are skipped."""
        added = 0
        for tag in tags:
            if any(existing.matches(tag.name) for existing in self.tags):
                continue
            self.tags.append(tag)
            added += 1
        return added

    def remove_tags(self, tags: list[Tag]) -> int:
        """Detach tags from the item; unknown tags are ignored."""
        removed = 0
        for tag in tags:
            for index, existing in enumerate(self.tags):
                if existing.matches(tag.name):
                    del self.tags[index]
                    removed += 1
                    break
        return removed


class _PurchasableListMixin:
    """Archival and completion rules shared by shopping lists and wishlists."""

    items: list[Any]
    status: ItemStatus
    completed_at: datetime | None

    def is_completed(self) -> bool:
        """Return whether every item on the list has been purchased.

        An empty list is never completed: nothing has been bought yet, so
        there is no completion date to age out.
        """
        if not self.items:
            return False
        return all(item.status is ItemStatus.PURCHASED for item in self.items)

    def should_archive(
        self,
        current_date: datetime,
        archive_delay: ArchiveDelay | Decimal | int | None = None,
    ) -> bool:
        """Return whether the completed list is old enough to be soft-deleted."""
        delay = _coerce_archive_delay(archive_delay)
        _require_aware(current_date, "Current date")
        if not self.is_completed() or self.completed_at is None:
            return False
        _require_aware(self.completed_at, "Completion")
        elapsed = current_date - self.completed_at
        return elapsed > timedelta(days=float(delay.days))

    def mark_as_completed(self, *, now: datetime) -> None:
        """Complete the list, stamping the completion date."""
        _require_aware(now, "List")
        self.status = ItemStatus.PURCHASED
        self.completed_at = now

    def mark_as_pending(self) -> None:
        """Reopen the list, clearing its completion date."""
        self.status = ItemStatus.PENDING
        self.completed_at = None

    def refresh_status(self, *, now: datetime) -> bool:
        """Recompute the list status from its items and return whether it changed.

        Completing the list stamps ``now`` as the completion date; reopening it
        clears the date so the list is never archived on a stale stamp.
        """
        was_completed = self.is_completed()
        if was_completed:
            if self.status is not ItemStatus.PURCHASED or self.completed_at is None:
                self.mark_as_completed(now=now)
                return True
            return False
        if self.status is ItemStatus.PURCHASED or self.completed_at is not None:
            self.mark_as_pending()
            return True
        return False

    def soft_delete(self) -> None:
        """Hide the list from the owner's default views."""
        self.is_active = False

    def restore(self) -> None:
        """Bring a soft-deleted list back."""
        self.is_active = True

    def _remove_item(self, item_id: UUID, not_found: type[Exception]) -> None:
        for index, item in enumerate(self.items):
            if item.id is not None and item.id.value == item_id:
                del self.items[index]
                return
        raise not_found("Item does not belong to this list.")


def _coerce_archive_delay(
    archive_delay: ArchiveDelay | Decimal | int | None,
) -> ArchiveDelay:
    """Accept an ``ArchiveDelay`` or a raw number of days."""
    if archive_delay is None:
        return ArchiveDelay(DEFAULT_ARCHIVE_DELAY)
    if isinstance(archive_delay, ArchiveDelay):
        return archive_delay
    try:
        return ArchiveDelay(archive_delay)
    except InvalidArchiveDelay:
        raise


@dataclass(eq=False, slots=True)
class ShoppingList(_PurchasableListMixin):
    """A named group of things to buy, owned by a single user."""

    user_id: UserId
    name: str
    created_at: datetime
    id: ShoppingListId | None = None
    priority: ListPriority = ListPriority.MEDIUM
    status: ItemStatus = ItemStatus.PENDING
    is_active: bool = True
    completed_at: datetime | None = None
    items: list[ShoppingListItem] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        name: str,
        now: datetime,
        priority: ListPriority = ListPriority.MEDIUM,
        tags: list[Tag] | None = None,
    ) -> "ShoppingList":
        """Create a shopping list after validating aggregate invariants."""
        if not isinstance(user_id, UserId):
            raise TypeError("Shopping list owner must be a UserId.")
        if not isinstance(priority, ListPriority):
            raise ValueError("Shopping list priority is invalid.")
        _require_aware(now, "Shopping list")
        return cls(
            id=None,
            user_id=user_id,
            name=_normalize_name(
                name, limit=MAX_LIST_NAME_LENGTH, label="Shopping list name"
            ),
            priority=priority,
            status=ItemStatus.PENDING,
            is_active=True,
            created_at=now,
            completed_at=None,
            tags=list(tags) if tags else [],
        )

    def rename(self, name: str) -> None:
        """Change the list display name."""
        self.name = _normalize_name(
            name, limit=MAX_LIST_NAME_LENGTH, label="Shopping list name"
        )

    def change_priority(self, priority: ListPriority) -> None:
        """Change the importance assigned to the list."""
        if not isinstance(priority, ListPriority):
            raise ValueError("Shopping list priority is invalid.")
        self.priority = priority

    def add_tags(self, tags: list[Tag]) -> int:
        """Associate tags with the list; already attached tags are skipped."""
        added = 0
        for tag in tags:
            if any(existing.matches(tag.name) for existing in self.tags):
                continue
            self.tags.append(tag)
            added += 1
        return added

    def remove_tags(self, tags: list[Tag]) -> int:
        """Detach tags from the list; unknown tags are ignored."""
        removed = 0
        for tag in tags:
            for index, existing in enumerate(self.tags):
                if existing.matches(tag.name):
                    del self.tags[index]
                    removed += 1
                    break
        return removed

    def add_item(self, item: ShoppingListItem) -> None:
        """Attach an item to the list."""
        if not isinstance(item, ShoppingListItem):
            raise TypeError("Shopping list item must be a ShoppingListItem.")
        if self.id is not None and item.shopping_list_id != self.id:
            raise ValueError("Item belongs to a different shopping list.")
        self.items.append(item)

    def remove_item(self, item_id: UUID) -> None:
        """Detach an item from the list."""
        self._remove_item(item_id, ShoppingListItemNotFound)

    def get_item(self, item_id: UUID) -> ShoppingListItem:
        """Return one of the list items by identity."""
        for item in self.items:
            if item.id is not None and item.id.value == item_id:
                return item
        raise ShoppingListItemNotFound("Item does not belong to this shopping list.")


@dataclass(eq=False, slots=True)
class Wishlist(_PurchasableListMixin):
    """The single wishlist owned by a user."""

    user_id: UserId
    name: str
    created_at: datetime
    id: WishlistId | None = None
    status: ItemStatus = ItemStatus.PENDING
    is_active: bool = True
    completed_at: datetime | None = None
    items: list[WishlistItem] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        name: str = DEFAULT_WISHLIST_NAME,
        now: datetime,
    ) -> "Wishlist":
        """Create a wishlist after validating aggregate invariants."""
        if not isinstance(user_id, UserId):
            raise TypeError("Wishlist owner must be a UserId.")
        _require_aware(now, "Wishlist")
        return cls(
            id=None,
            user_id=user_id,
            name=_normalize_name(
                name, limit=MAX_LIST_NAME_LENGTH, label="Wishlist name"
            ),
            status=ItemStatus.PENDING,
            is_active=True,
            created_at=now,
            completed_at=None,
        )

    def rename(self, name: str) -> None:
        """Change the wishlist display name."""
        self.name = _normalize_name(
            name, limit=MAX_LIST_NAME_LENGTH, label="Wishlist name"
        )

    def add_item(self, item: WishlistItem) -> None:
        """Attach an item to the wishlist."""
        if not isinstance(item, WishlistItem):
            raise TypeError("Wishlist item must be a WishlistItem.")
        if self.id is not None and item.wishlist_id != self.id:
            raise ValueError("Item belongs to a different wishlist.")
        self.items.append(item)

    def remove_item(self, item_id: UUID) -> None:
        """Detach an item from the wishlist."""
        self._remove_item(item_id, WishlistItemNotFound)

    def get_item(self, item_id: UUID) -> WishlistItem:
        """Return one of the wishlist items by identity."""
        for item in self.items:
            if item.id is not None and item.id.value == item_id:
                return item
        raise WishlistItemNotFound("Item does not belong to this wishlist.")
