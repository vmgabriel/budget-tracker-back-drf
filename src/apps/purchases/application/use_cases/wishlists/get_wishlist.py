"""Wishlist retrieval use case."""

from apps.purchases.application.commands import GetOrCreateWishlistCommand
from apps.purchases.application.dto import WishlistDetails, wishlist_details
from apps.purchases.application.ports.repositories import (
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.application.scope import resolve_wishlist_items
from apps.purchases.domain.entities import Wishlist
from apps.purchases.domain.exceptions import (
    PurchasesDomainError,
    WishlistAlreadyExists,
    WishlistNotFound,
)
from apps.purchases.domain.value_objects import UserId
from shared.domain.ports.clock import Clock


class GetOrCreateWishlist:
    """Return the user's wishlist, creating the single one on first access.

    A user owns at most one wishlist, so the create path can race with itself
    (two parallel first requests). The adapter's one-to-one constraint then
    rejects the loser, which is reported as ``WishlistAlreadyExists`` rather
    than an opaque integrity error.
    """

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
        clock: Clock,
    ) -> None:
        self._wishlists = wishlists
        self._items = items
        self._clock = clock

    def execute(self, command: GetOrCreateWishlistCommand) -> WishlistDetails:
        user_id = UserId(value=command.user_id)
        wishlist = self._wishlists.get_by_user_id(user_id)
        if wishlist is not None:
            return wishlist_details(
                wishlist, resolve_wishlist_items(wishlist, self._items)
            )
        try:
            wishlist = Wishlist.create(user_id=user_id, now=self._clock.now())
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise WishlistAlreadyExists("This user already has a wishlist.") from error
        return wishlist_details(self._wishlists.save(wishlist))


class GetWishlist:
    """Return the requesting user's wishlist without creating one."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
    ) -> None:
        self._wishlists = wishlists
        self._items = items

    def execute(self, command: GetOrCreateWishlistCommand) -> WishlistDetails:
        wishlist = self._wishlists.get_by_user_id(UserId(value=command.user_id))
        if wishlist is None:
            raise WishlistNotFound("Wishlist not found.")
        return wishlist_details(wishlist, resolve_wishlist_items(wishlist, self._items))
