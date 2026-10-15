"""Wishlist update use case."""

from apps.purchases.application.commands import UpdateWishlistCommand
from apps.purchases.application.dto import WishlistDetails, wishlist_details
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.ports.repositories import WishlistRepository
from apps.purchases.application.scope import require_wishlist_for_owner
from apps.purchases.domain.exceptions import PurchasesDomainError
from apps.purchases.domain.value_objects import WishlistId


class UpdateWishlist:
    """Apply partial changes to the wishlist owned by the requesting user."""

    def __init__(self, wishlists: WishlistRepository) -> None:
        self._wishlists = wishlists

    def execute(self, command: UpdateWishlistCommand) -> WishlistDetails:
        if command.name is None:
            raise InvalidPurchasesInput("At least one wishlist field is required.")

        wishlist = require_wishlist_for_owner(
            self._wishlists, WishlistId(command.wishlist_id), command.user_id
        )
        try:
            wishlist.rename(command.name)
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return wishlist_details(self._wishlists.update(wishlist))
