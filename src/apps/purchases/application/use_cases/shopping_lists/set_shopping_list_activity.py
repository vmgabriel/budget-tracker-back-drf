"""Shopping list soft-delete and restore use cases."""

from apps.purchases.application.commands import (
    RestoreShoppingListCommand,
    SoftDeleteShoppingListCommand,
)
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.ports.repositories import ShoppingListRepository
from apps.purchases.application.scope import require_shopping_list_for_owner
from apps.purchases.domain.value_objects import ShoppingListId


class SoftDeleteShoppingList:
    """Hide a shopping list without discarding its items."""

    def __init__(self, shopping_lists: ShoppingListRepository) -> None:
        self._shopping_lists = shopping_lists

    def execute(self, command: SoftDeleteShoppingListCommand) -> ShoppingListDetails:
        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, ShoppingListId(command.list_id), command.user_id
        )
        shopping_list.soft_delete()
        self._shopping_lists.soft_delete(ShoppingListId(command.list_id))
        return shopping_list_details(shopping_list)


class RestoreShoppingList:
    """Bring a soft-deleted shopping list back."""

    def __init__(self, shopping_lists: ShoppingListRepository) -> None:
        self._shopping_lists = shopping_lists

    def execute(self, command: RestoreShoppingListCommand) -> ShoppingListDetails:
        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, ShoppingListId(command.list_id), command.user_id
        )
        shopping_list.restore()
        self._shopping_lists.restore(ShoppingListId(command.list_id))
        return shopping_list_details(shopping_list)
