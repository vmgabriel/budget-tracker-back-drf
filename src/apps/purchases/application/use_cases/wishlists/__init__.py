"""Wishlist use cases."""

from apps.purchases.application.use_cases.wishlists.add_item_to_wishlist import (
    AddItemToWishlist,
)
from apps.purchases.application.use_cases.wishlists.get_wishlist import (
    GetOrCreateWishlist,
    GetWishlist,
)
from apps.purchases.application.use_cases.wishlists.mark_wishlist_item_as_purchased import (
    MarkWishlistItemAsPurchased,
)
from apps.purchases.application.use_cases.wishlists.update_wishlist import (
    UpdateWishlist,
)
from apps.purchases.application.use_cases.wishlists.update_wishlist_item import (
    DeleteWishlistItem,
    UpdateWishlistItem,
)
from apps.purchases.application.use_cases.wishlists.wishlist_item_tags import (
    AddTagsToWishlistItem,
    RemoveTagsFromWishlistItem,
)

__all__ = (
    "AddItemToWishlist",
    "AddTagsToWishlistItem",
    "DeleteWishlistItem",
    "GetOrCreateWishlist",
    "GetWishlist",
    "MarkWishlistItemAsPurchased",
    "RemoveTagsFromWishlistItem",
    "UpdateWishlist",
    "UpdateWishlistItem",
)
