"""Commands accepted by purchases use cases.

Commands are frozen dataclasses carrying only primitives: interfaces parse
request payloads into them, and the use cases build the domain value objects.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID

# ---------------------------------------------------------------------------
# Shopping lists
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateShoppingListCommand:
    """Input accepted when creating a shopping list."""

    user_id: UUID
    name: str
    priority: str = "medium"


@dataclass(frozen=True, slots=True)
class UpdateShoppingListCommand:
    """Partial input accepted when updating a shopping list.

    ``None`` leaves a field unchanged.
    """

    list_id: UUID
    user_id: UUID
    name: str | None = None
    priority: str | None = None


@dataclass(frozen=True, slots=True)
class ListShoppingListsCommand:
    """Input accepted when listing a user's shopping lists."""

    user_id: UUID


@dataclass(frozen=True, slots=True)
class GetShoppingListCommand:
    """Input accepted when retrieving one shopping list."""

    list_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class SoftDeleteShoppingListCommand:
    """Input accepted when soft-deleting a shopping list."""

    list_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class RestoreShoppingListCommand:
    """Input accepted when restoring a soft-deleted shopping list."""

    list_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class AddItemToShoppingListCommand:
    """Input accepted when adding an item to a shopping list."""

    list_id: UUID
    user_id: UUID
    name: str
    quantity: int = 1
    details: str | None = None


@dataclass(frozen=True, slots=True)
class UpdateShoppingListItemCommand:
    """Partial input accepted when updating a shopping list item."""

    item_id: UUID
    user_id: UUID
    name: str | None = None
    quantity: int | None = None
    details: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteShoppingListItemCommand:
    """Input accepted when deleting a shopping list item."""

    item_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class MarkItemAsPurchasedCommand:
    """Input accepted when flagging a shopping list item as bought."""

    item_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class AddTagsToItemCommand:
    """Input accepted when tagging a shopping list item."""

    item_id: UUID
    user_id: UUID
    tag_names: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RemoveTagsFromItemCommand:
    """Input accepted when untagging a shopping list item.

    Tags are addressed by identity; unknown ids are reported by the use case
    rather than silently ignored.
    """

    item_id: UUID
    user_id: UUID
    tag_ids: list[UUID] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetOrCreateWishlistCommand:
    """Input accepted when fetching the user's wishlist, creating it if absent."""

    user_id: UUID


@dataclass(frozen=True, slots=True)
class UpdateWishlistCommand:
    """Partial input accepted when updating the wishlist."""

    wishlist_id: UUID
    user_id: UUID
    name: str | None = None


@dataclass(frozen=True, slots=True)
class AddItemToWishlistCommand:
    """Input accepted when adding an item to the wishlist."""

    wishlist_id: UUID
    user_id: UUID
    name: str
    link: str | None = None
    image_link: str | None = None
    description: str | None = None
    estimated_price: Decimal | None = None
    priority: str = "wanted"


@dataclass(frozen=True, slots=True)
class UpdateWishlistItemCommand:
    """Partial input accepted when updating a wishlist item."""

    item_id: UUID
    user_id: UUID
    name: str | None = None
    link: str | None = None
    image_link: str | None = None
    description: str | None = None
    estimated_price: Decimal | None = None
    priority: str | None = None


@dataclass(frozen=True, slots=True)
class DeleteWishlistItemCommand:
    """Input accepted when deleting a wishlist item."""

    item_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class MarkWishlistItemAsPurchasedCommand:
    """Input accepted when flagging a wishlist item as bought."""

    item_id: UUID
    user_id: UUID


@dataclass(frozen=True, slots=True)
class AddTagsToWishlistItemCommand:
    """Input accepted when tagging a wishlist item."""

    item_id: UUID
    user_id: UUID
    tag_names: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RemoveTagsFromWishlistItemCommand:
    """Input accepted when untagging a wishlist item."""

    item_id: UUID
    user_id: UUID
    tag_ids: list[UUID] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CreateTagCommand:
    """Input accepted when adding a tag to the catalogue."""

    name: str


@dataclass(frozen=True, slots=True)
class ListTagsCommand:
    """Input accepted when listing the tag catalogue."""
