"""Shopping list item deletion use case."""

from apps.purchases.application.commands import DeleteShoppingListItemCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
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


class DeleteShoppingListItem:
    """Remove an item and re-evaluate the completion state of its list.

    Deleting the item that completed a list reopens it, so the parent list is
    re-stamped rather than left claiming every item was bought.
    """

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
        clock: Clock,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items
        self._clock = clock

    def execute(self, command: DeleteShoppingListItemCommand) -> ShoppingListDetails:
        item_id = ShoppingListItemId(command.item_id)
        item = require_shopping_list_item_for_owner(
            self._items, self._shopping_lists, item_id, command.user_id
        )
        self._items.delete(item_id)

        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, item.shopping_list_id, command.user_id
        )
        shopping_list.items = resolve_shopping_list_items(shopping_list, self._items)
        shopping_list.refresh_status(now=self._clock.now())
        return shopping_list_details(
            self._shopping_lists.update(shopping_list), shopping_list.items
        )
