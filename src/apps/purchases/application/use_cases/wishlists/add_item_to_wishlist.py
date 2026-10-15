"""Add-item use case for the wishlist."""

from apps.purchases.application.commands import AddItemToWishlistCommand
from apps.purchases.application.dto import WishlistDetails, wishlist_details
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.parsing import (
    parse_estimated_price,
    parse_link,
    parse_wishlist_priority,
)
from apps.purchases.application.ports.repositories import (
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.application.scope import require_wishlist_for_owner
from apps.purchases.domain.entities import WishlistItem
from apps.purchases.domain.exceptions import (
    PurchasesDomainError,
    WishlistNotFound,
)
from apps.purchases.domain.value_objects import WishlistId


class AddItemToWishlist:
    """Add a wanted product to the wishlist owned by the requesting user."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
    ) -> None:
        self._wishlists = wishlists
        self._items = items

    def execute(self, command: AddItemToWishlistCommand) -> WishlistDetails:
        wishlist = require_wishlist_for_owner(
            self._wishlists, WishlistId(command.wishlist_id), command.user_id
        )
        if wishlist.id is None:
            raise WishlistNotFound("Wishlist not found.")
        try:
            item = WishlistItem.create(
                wishlist_id=wishlist.id,
                name=command.name,
                link=(parse_link(command.link, "Link") if command.link else None),
                image_link=(
                    parse_link(command.image_link, "Image link")
                    if command.image_link
                    else None
                ),
                description=command.description,
                estimated_price=(
                    parse_estimated_price(command.estimated_price)
                    if command.estimated_price is not None
                    else None
                ),
                priority=parse_wishlist_priority(command.priority),
            )
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        self._items.save(item)
        wishlist.add_item(item)
        return wishlist_details(self._wishlists.update(wishlist))
