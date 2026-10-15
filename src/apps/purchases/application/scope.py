"""Owner-scoping helpers shared by purchases use cases.

Every helper raises the matching ``*NotFound`` when a resource is missing *or*
owned by somebody else, so a foreign resource is indistinguishable from a
non-existent one at the HTTP layer.
"""

from uuid import UUID

from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.exceptions import (
    ShoppingListItemNotFound,
    ShoppingListNotFound,
    WishlistItemNotFound,
    WishlistNotFound,
)
from apps.purchases.domain.value_objects import (
    ShoppingListId,
    ShoppingListItemId,
    WishlistId,
    WishlistItemId,
)


def require_shopping_list_for_owner(
    shopping_lists: ShoppingListRepository,
    shopping_list_id: ShoppingListId,
    owner_id: UUID,
) -> ShoppingList:
    """Return the list only when it exists and belongs to ``owner_id``."""
    shopping_list = shopping_lists.get_by_id(shopping_list_id)
    if shopping_list is None or shopping_list.user_id.value != owner_id:
        raise ShoppingListNotFound("Shopping list not found.")
    return shopping_list


def require_wishlist_for_owner(
    wishlists: WishlistRepository, wishlist_id: WishlistId, owner_id: UUID
) -> Wishlist:
    """Return the wishlist only when it exists and belongs to ``owner_id``."""
    wishlist = wishlists.get_by_id(wishlist_id)
    if wishlist is None or wishlist.user_id.value != owner_id:
        raise WishlistNotFound("Wishlist not found.")
    return wishlist


def require_shopping_list_item_for_owner(
    items: ShoppingListItemRepository,
    shopping_lists: ShoppingListRepository,
    item_id: ShoppingListItemId,
    owner_id: UUID,
) -> ShoppingListItem:
    """Return the item only when its list belongs to ``owner_id``.

    The item carries no owner of its own, so ownership is resolved through the
    parent list in a second lookup.
    """
    item = items.get_by_id(item_id)
    if item is None:
        raise ShoppingListItemNotFound("Shopping list item not found.")
    shopping_list = shopping_lists.get_by_id(item.shopping_list_id)
    if shopping_list is None or shopping_list.user_id.value != owner_id:
        raise ShoppingListItemNotFound("Shopping list item not found.")
    return item


def require_wishlist_item_for_owner(
    items: WishlistItemRepository,
    wishlists: WishlistRepository,
    item_id: WishlistItemId,
    owner_id: UUID,
) -> WishlistItem:
    """Return the item only when its wishlist belongs to ``owner_id``."""
    item = items.get_by_id(item_id)
    if item is None:
        raise WishlistItemNotFound("Wishlist item not found.")
    wishlist = wishlists.get_by_id(item.wishlist_id)
    if wishlist is None or wishlist.user_id.value != owner_id:
        raise WishlistItemNotFound("Wishlist item not found.")
    return item


def resolve_shopping_list_items(
    shopping_list: ShoppingList, items: ShoppingListItemRepository
) -> list[ShoppingListItem]:
    """Hydrate the items of a persisted list through its repository."""
    if shopping_list.id is None:
        raise ShoppingListNotFound("Shopping list not found.")
    return items.get_by_list_id(shopping_list.id)


def resolve_wishlist_items(
    wishlist: Wishlist, items: WishlistItemRepository
) -> list[WishlistItem]:
    """Hydrate the items of a persisted wishlist through its repository."""
    if wishlist.id is None:
        raise WishlistNotFound("Wishlist not found.")
    return items.get_by_wishlist_id(wishlist.id)
