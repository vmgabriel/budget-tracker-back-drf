"""Tag association use cases for shopping list items.

Tags live in a shared catalogue. Adding resolves names through
``TagRepository.get_or_create`` so the catalogue never accumulates near
duplicates, and removing addresses tags by identity.
"""

from apps.purchases.application.commands import (
    AddTagsToItemCommand,
    RemoveTagsFromItemCommand,
)
from apps.purchases.application.dto import (
    ShoppingListItemDetails,
    shopping_list_item_details,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
    TagRepository,
)
from apps.purchases.application.scope import require_shopping_list_item_for_owner
from apps.purchases.domain.entities import Tag
from apps.purchases.domain.exceptions import PurchasesDomainError, TagNotFound
from apps.purchases.domain.value_objects import ShoppingListItemId, TagId


class AddTagsToItem:
    """Associate catalogue tags with an item; already attached tags are kept once."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
        tags: TagRepository,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items
        self._tags = tags

    def execute(self, command: AddTagsToItemCommand) -> ShoppingListItemDetails:
        names = [name.strip() for name in command.tag_names if name.strip()]
        if not names:
            raise InvalidPurchasesInput("At least one tag name is required.")

        item = require_shopping_list_item_for_owner(
            self._items,
            self._shopping_lists,
            ShoppingListItemId(command.item_id),
            command.user_id,
        )
        try:
            item.add_tags([self._tags.get_or_create(name) for name in names])
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return shopping_list_item_details(self._items.update(item))


class RemoveTagsFromItem:
    """Detach tags from an item; unknown tag ids are reported, not ignored."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
        tags: TagRepository,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items
        self._tags = tags

    def execute(self, command: RemoveTagsFromItemCommand) -> ShoppingListItemDetails:
        if not command.tag_ids:
            raise InvalidPurchasesInput("At least one tag id is required.")

        item = require_shopping_list_item_for_owner(
            self._items,
            self._shopping_lists,
            ShoppingListItemId(command.item_id),
            command.user_id,
        )
        resolved: list[Tag] = []
        for raw_tag_id in command.tag_ids:
            tag = self._tags.get_by_id(TagId(raw_tag_id))
            if tag is None:
                raise TagNotFound("Tag not found.")
            resolved.append(tag)
        item.remove_tags(resolved)
        return shopping_list_item_details(self._items.update(item))
