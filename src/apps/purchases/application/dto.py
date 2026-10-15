"""Application-layer representations safe to return from interfaces."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Tag,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.value_objects import (
    ItemStatus,
    ListPriority,
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    WishlistId,
    WishlistItemId,
    WishlistPriority,
)


@dataclass(frozen=True, slots=True)
class TagDetails:
    """Tag data safe to expose through an HTTP interface."""

    id: TagId
    name: str
    slug: str


@dataclass(frozen=True, slots=True)
class ShoppingListItemDetails:
    """Shopping list item data safe to expose through an HTTP interface."""

    id: ShoppingListItemId
    name: str
    quantity: int
    details: str | None
    status: ItemStatus
    tags: list[TagDetails]


@dataclass(frozen=True, slots=True)
class ShoppingListDetails:
    """Shopping list data safe to expose through an HTTP interface."""

    id: ShoppingListId
    name: str
    priority: ListPriority
    status: ItemStatus
    is_active: bool
    created_at: datetime
    completed_at: datetime | None
    items: list[ShoppingListItemDetails]
    tags: list[TagDetails]


@dataclass(frozen=True, slots=True)
class WishlistItemDetails:
    """Wishlist item data safe to expose through an HTTP interface."""

    id: WishlistItemId
    name: str
    link: str | None
    image_link: str | None
    description: str | None
    estimated_price: Decimal | None
    priority: WishlistPriority
    status: ItemStatus
    tags: list[TagDetails]


@dataclass(frozen=True, slots=True)
class WishlistDetails:
    """Wishlist data safe to expose through an HTTP interface."""

    id: WishlistId
    name: str
    status: ItemStatus
    is_active: bool
    created_at: datetime
    completed_at: datetime | None
    items: list[WishlistItemDetails]


def tag_details(tag: Tag) -> TagDetails:
    """Convert a persisted tag into a safe result."""
    if tag.id is None:
        raise ValueError("A persisted tag must have an identity.")
    return TagDetails(id=tag.id, name=tag.name, slug=tag.slug)


def tag_details_list(tags: list[Tag]) -> list[TagDetails]:
    """Convert a collection of tags into safe results."""
    return [tag_details(tag) for tag in tags]


def shopping_list_item_details(
    item: ShoppingListItem,
    tags: list[Tag] | None = None,
) -> ShoppingListItemDetails:
    """Convert a persisted shopping list item into a safe result."""
    if item.id is None:
        raise ValueError("A persisted shopping list item must have an identity.")
    return ShoppingListItemDetails(
        id=item.id,
        name=item.name,
        quantity=int(item.quantity),
        details=item.details,
        status=item.status,
        tags=tag_details_list(item.tags if tags is None else tags),
    )


def shopping_list_item_details_list(
    items: list[ShoppingListItem],
) -> list[ShoppingListItemDetails]:
    """Convert a collection of shopping list items into safe results."""
    return [shopping_list_item_details(item) for item in items]


def shopping_list_details(
    shopping_list: ShoppingList,
    items: list[ShoppingListItem] | None = None,
    tags: list[Tag] | None = None,
) -> ShoppingListDetails:
    """Convert a persisted shopping list into a safe result.

    ``items`` and ``tags`` default to what the aggregate already carries, so a
    repository that hydrates the full aggregate needs no extra arguments.
    """
    if shopping_list.id is None:
        raise ValueError("A persisted shopping list must have an identity.")
    resolved_items = shopping_list.items if items is None else items
    return ShoppingListDetails(
        id=shopping_list.id,
        name=shopping_list.name,
        priority=shopping_list.priority,
        status=shopping_list.status,
        is_active=shopping_list.is_active,
        created_at=shopping_list.created_at,
        completed_at=shopping_list.completed_at,
        items=shopping_list_item_details_list(resolved_items),
        tags=tag_details_list(shopping_list.tags if tags is None else tags),
    )


def wishlist_item_details(
    item: WishlistItem,
    tags: list[Tag] | None = None,
) -> WishlistItemDetails:
    """Convert a persisted wishlist item into a safe result."""
    if item.id is None:
        raise ValueError("A persisted wishlist item must have an identity.")
    return WishlistItemDetails(
        id=item.id,
        name=item.name,
        link=str(item.link) if item.link is not None else None,
        image_link=str(item.image_link) if item.image_link is not None else None,
        description=item.description,
        estimated_price=(
            item.estimated_price.amount if item.estimated_price is not None else None
        ),
        priority=item.priority,
        status=item.status,
        tags=tag_details_list(item.tags if tags is None else tags),
    )


def wishlist_item_details_list(items: list[WishlistItem]) -> list[WishlistItemDetails]:
    """Convert a collection of wishlist items into safe results."""
    return [wishlist_item_details(item) for item in items]


def wishlist_details(
    wishlist: Wishlist,
    items: list[WishlistItem] | None = None,
) -> WishlistDetails:
    """Convert a persisted wishlist into a safe result."""
    if wishlist.id is None:
        raise ValueError("A persisted wishlist must have an identity.")
    resolved_items = wishlist.items if items is None else items
    return WishlistDetails(
        id=wishlist.id,
        name=wishlist.name,
        status=wishlist.status,
        is_active=wishlist.is_active,
        created_at=wishlist.created_at,
        completed_at=wishlist.completed_at,
        items=wishlist_item_details_list(resolved_items),
    )
