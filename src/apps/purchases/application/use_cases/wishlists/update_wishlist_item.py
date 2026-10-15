"""Update and delete use cases for wishlist items."""

from apps.purchases.application.commands import (
    DeleteWishlistItemCommand,
    UpdateWishlistItemCommand,
)
from apps.purchases.application.dto import (
    WishlistDetails,
    WishlistItemDetails,
    wishlist_details,
    wishlist_item_details,
)
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
from apps.purchases.application.scope import (
    require_wishlist_for_owner,
    require_wishlist_item_for_owner,
    resolve_wishlist_items,
)
from apps.purchases.domain.exceptions import PurchasesDomainError
from apps.purchases.domain.value_objects import WishlistItemId
from shared.domain.ports.clock import Clock


class UpdateWishlistItem:
    """Apply partial changes to a wishlist item the requesting user owns."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
    ) -> None:
        self._wishlists = wishlists
        self._items = items

    def execute(self, command: UpdateWishlistItemCommand) -> WishlistItemDetails:
        if (
            command.name is None
            and command.link is None
            and command.image_link is None
            and command.description is None
            and command.estimated_price is None
            and command.priority is None
        ):
            raise InvalidPurchasesInput("At least one item field is required.")

        item = require_wishlist_item_for_owner(
            self._items,
            self._wishlists,
            WishlistItemId(command.item_id),
            command.user_id,
        )
        try:
            item.update(
                name=command.name,
                link=parse_link(command.link, "Link") if command.link else None,
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
                priority=(
                    parse_wishlist_priority(command.priority)
                    if command.priority is not None
                    else None
                ),
            )
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return wishlist_item_details(self._items.update(item))


class DeleteWishlistItem:
    """Remove a wishlist item and re-evaluate the completion of its wishlist."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
        clock: Clock,
    ) -> None:
        self._wishlists = wishlists
        self._items = items
        self._clock = clock

    def execute(self, command: DeleteWishlistItemCommand) -> WishlistDetails:
        item_id = WishlistItemId(command.item_id)
        item = require_wishlist_item_for_owner(
            self._items, self._wishlists, item_id, command.user_id
        )
        self._items.delete(item_id)

        wishlist = require_wishlist_for_owner(
            self._wishlists, item.wishlist_id, command.user_id
        )
        wishlist.items = resolve_wishlist_items(wishlist, self._items)
        wishlist.refresh_status(now=self._clock.now())
        return wishlist_details(self._wishlists.update(wishlist), wishlist.items)
