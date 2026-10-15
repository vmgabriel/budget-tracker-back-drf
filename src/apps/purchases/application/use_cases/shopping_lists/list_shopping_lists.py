"""Shopping list listing use cases."""

from apps.purchases.application.commands import ListShoppingListsCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.ports.repositories import ShoppingListRepository
from apps.purchases.domain.value_objects import UserId


class ListUserShoppingLists:
    """Return the active shopping lists of the requesting user."""

    def __init__(self, shopping_lists: ShoppingListRepository) -> None:
        self._shopping_lists = shopping_lists

    def execute(self, command: ListShoppingListsCommand) -> list[ShoppingListDetails]:
        shopping_lists = self._shopping_lists.get_by_user_id(
            UserId(value=command.user_id), active_only=True
        )
        return [
            shopping_list_details(shopping_list) for shopping_list in shopping_lists
        ]


class ListInactiveShoppingLists:
    """Return the soft-deleted shopping lists of the requesting user."""

    def __init__(self, shopping_lists: ShoppingListRepository) -> None:
        self._shopping_lists = shopping_lists

    def execute(self, command: ListShoppingListsCommand) -> list[ShoppingListDetails]:
        shopping_lists = self._shopping_lists.get_by_user_id(
            UserId(value=command.user_id), active_only=False
        )
        return [
            shopping_list_details(shopping_list)
            for shopping_list in shopping_lists
            if not shopping_list.is_active
        ]
