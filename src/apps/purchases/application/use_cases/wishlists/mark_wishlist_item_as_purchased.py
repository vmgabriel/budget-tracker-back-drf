"""Wishlist item purchase use case."""

from apps.purchases.application.commands import MarkWishlistItemAsPurchasedCommand
from apps.purchases.application.dto import WishlistDetails, wishlist_details
from apps.purchases.application.ports.repositories import (
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.application.scope import (
    require_wishlist_for_owner,
    require_wishlist_item_for_owner,
    resolve_wishlist_items,
)
from apps.purchases.domain.value_objects import WishlistItemId
from shared.domain.ports.clock import Clock


class MarkWishlistItemAsPurchased:
    """Flag a wishlist item as bought and re-evaluate the parent wishlist."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
        clock: Clock,
    ) -> None:
        self._wishlists = wishlists
        self._items = items
        self._clock = clock

    def execute(self, command: MarkWishlistItemAsPurchasedCommand) -> WishlistDetails:
        item = require_wishlist_item_for_owner(
            self._items,
            self._wishlists,
            WishlistItemId(command.item_id),
            command.user_id,
        )
        item.mark_as_purchased()
        self._items.update(item)

        wishlist = require_wishlist_for_owner(
            self._wishlists, item.wishlist_id, command.user_id
        )
        wishlist.items = resolve_wishlist_items(wishlist, self._items)
        wishlist.refresh_status(now=self._clock.now())
        return wishlist_details(self._wishlists.update(wishlist), wishlist.items)
