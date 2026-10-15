"""Shopping list update use case."""

from apps.purchases.application.commands import UpdateShoppingListCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.parsing import parse_list_priority
from apps.purchases.application.ports.repositories import ShoppingListRepository
from apps.purchases.application.scope import require_shopping_list_for_owner
from apps.purchases.domain.exceptions import PurchasesDomainError
from apps.purchases.domain.value_objects import ShoppingListId


class UpdateShoppingList:
    """Apply partial changes to a shopping list owned by the requesting user."""

    def __init__(self, shopping_lists: ShoppingListRepository) -> None:
        self._shopping_lists = shopping_lists

    def execute(self, command: UpdateShoppingListCommand) -> ShoppingListDetails:
        if command.name is None and command.priority is None:
            raise InvalidPurchasesInput("At least one shopping list field is required.")

        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, ShoppingListId(command.list_id), command.user_id
        )
        try:
            if command.name is not None:
                shopping_list.rename(command.name)
            if command.priority is not None:
                shopping_list.change_priority(parse_list_priority(command.priority))
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return shopping_list_details(self._shopping_lists.update(shopping_list))
