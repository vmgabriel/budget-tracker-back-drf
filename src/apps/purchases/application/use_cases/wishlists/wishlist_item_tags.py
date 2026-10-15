"""Tag association use cases for wishlist items."""

from apps.purchases.application.commands import (
    AddTagsToWishlistItemCommand,
    RemoveTagsFromWishlistItemCommand,
)
from apps.purchases.application.dto import (
    WishlistItemDetails,
    wishlist_item_details,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.ports.repositories import (
    TagRepository,
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.application.scope import require_wishlist_item_for_owner
from apps.purchases.domain.entities import Tag
from apps.purchases.domain.exceptions import PurchasesDomainError, TagNotFound
from apps.purchases.domain.value_objects import TagId, WishlistItemId


class AddTagsToWishlistItem:
    """Associate catalogue tags with a wishlist item."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
        tags: TagRepository,
    ) -> None:
        self._wishlists = wishlists
        self._items = items
        self._tags = tags

    def execute(self, command: AddTagsToWishlistItemCommand) -> WishlistItemDetails:
        names = [name.strip() for name in command.tag_names if name.strip()]
        if not names:
            raise InvalidPurchasesInput("At least one tag name is required.")

        item = require_wishlist_item_for_owner(
            self._items,
            self._wishlists,
            WishlistItemId(command.item_id),
            command.user_id,
        )
        try:
            item.add_tags([self._tags.get_or_create(name) for name in names])
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return wishlist_item_details(self._items.update(item))


class RemoveTagsFromWishlistItem:
    """Detach tags from a wishlist item; unknown tag ids are reported."""

    def __init__(
        self,
        wishlists: WishlistRepository,
        items: WishlistItemRepository,
        tags: TagRepository,
    ) -> None:
        self._wishlists = wishlists
        self._items = items
        self._tags = tags

    def execute(
        self, command: RemoveTagsFromWishlistItemCommand
    ) -> WishlistItemDetails:
        if not command.tag_ids:
            raise InvalidPurchasesInput("At least one tag id is required.")

        item = require_wishlist_item_for_owner(
            self._items,
            self._wishlists,
            WishlistItemId(command.item_id),
            command.user_id,
        )
        resolved: list[Tag] = []
        for raw_tag_id in command.tag_ids:
            tag = self._tags.get_by_id(TagId(raw_tag_id))
            if tag is None:
                raise TagNotFound("Tag not found.")
            resolved.append(tag)
        item.remove_tags(resolved)
        return wishlist_item_details(self._items.update(item))
