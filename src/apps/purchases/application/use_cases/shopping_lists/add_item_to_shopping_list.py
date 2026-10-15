"""Add-item use case for shopping lists."""

from apps.purchases.application.commands import AddItemToShoppingListCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.parsing import parse_quantity
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
)
from apps.purchases.application.scope import require_shopping_list_for_owner
from apps.purchases.domain.entities import ShoppingListItem
from apps.purchases.domain.exceptions import (
    PurchasesDomainError,
    ShoppingListNotFound,
)
from apps.purchases.domain.value_objects import ShoppingListId


class AddItemToShoppingList:
    """Add an item to a shopping list owned by the requesting user."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items

    def execute(self, command: AddItemToShoppingListCommand) -> ShoppingListDetails:
        shopping_list = require_shopping_list_for_owner(
            self._shopping_lists, ShoppingListId(command.list_id), command.user_id
        )
        if shopping_list.id is None:
            raise ShoppingListNotFound("Shopping list not found.")
        try:
            item = ShoppingListItem.create(
                shopping_list_id=shopping_list.id,
                name=command.name,
                quantity=parse_quantity(command.quantity),
                details=command.details,
            )
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        self._items.save(item)
        shopping_list.add_item(item)
        return shopping_list_details(self._shopping_lists.update(shopping_list))
