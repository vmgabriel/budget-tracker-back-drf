"""Shopping list item purchase use case.

Buying the last outstanding item completes the parent list, so this is the one
item operation that writes to both the item and its list.
"""

from apps.purchases.application.commands import MarkItemAsPurchasedCommand
from apps.purchases.application.dto import (
    ShoppingListDetails,
    shopping_list_details,
)
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
)
from apps.purchases.application.scope import (
    require_shopping_list_for_owner,
    require_shopping_list_item_for_owner,
    resolve_shopping_list_items,
)
from apps.purchases.domain.value_objects import ShoppingListItemId
from shared.domain.ports.clock import Clock


class MarkItemAsPurchased:
    """Flag a shopping list item as bought and re-evaluate the parent list."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
        clock: Clock,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items
        self._clock = clock

    def execute(self, command: MarkItemAsPurchasedCommand) -> ShoppingListDetails:
        item = require_shopping_list_item_for_owner(
            self._items,
            self._shopping_lists,
            ShoppingListItemId(command.item_id),
            command.user_id,
        )
        item.mark_as_purchased()
        self._items.update(item)

        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, item.shopping_list_id, command.user_id
        )
        # Reload rather than trust the aggregate: a repository may return a
        # list whose items were never hydrated, and completion is a claim
        # about *every* item, not just the one just bought.
        shopping_list.items = resolve_shopping_list_items(shopping_list, self._items)
        shopping_list.refresh_status(now=self._clock.now())
        return shopping_list_details(
            self._shopping_lists.update(shopping_list), shopping_list.items
        )
