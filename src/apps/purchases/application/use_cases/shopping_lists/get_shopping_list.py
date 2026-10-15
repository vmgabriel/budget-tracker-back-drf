"""Shopping list retrieval use case."""

from apps.purchases.application.commands import GetShoppingListCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
)
from apps.purchases.application.scope import (
    require_shopping_list_for_owner,
    resolve_shopping_list_items,
)
from apps.purchases.domain.value_objects import ShoppingListId


class GetShoppingList:
    """Return one shopping list owned by the requesting user."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items

    def execute(self, command: GetShoppingListCommand) -> ShoppingListDetails:
        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, ShoppingListId(command.list_id), command.user_id
        )
        return shopping_list_details(
            shopping_list, resolve_shopping_list_items(shopping_list, self._items)
        )
