"""Update use case for shopping list items."""

from apps.purchases.application.commands import UpdateShoppingListItemCommand
from apps.purchases.application.dto import (
    ShoppingListItemDetails,
    shopping_list_item_details,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.parsing import parse_quantity
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
)
from apps.purchases.application.scope import require_shopping_list_item_for_owner
from apps.purchases.domain.exceptions import PurchasesDomainError
from apps.purchases.domain.value_objects import ShoppingListItemId


class UpdateShoppingListItem:
    """Apply partial changes to an item the requesting user owns."""

    def __init__(
        self,
        shopping_lists: ShoppingListRepository,
        items: ShoppingListItemRepository,
    ) -> None:
        self._shopping_lists = shopping_lists
        self._items = items

    def execute(
        self, command: UpdateShoppingListItemCommand
    ) -> ShoppingListItemDetails:
        if (
            command.name is None
            and command.quantity is None
            and command.details is None
        ):
            raise InvalidPurchasesInput("At least one item field is required.")

        item = require_shopping_list_item_for_owner(
            self._items,
            self._shopping_lists,
            ShoppingListItemId(command.item_id),
            command.user_id,
        )
        try:
            item.update(
                name=command.name,
                quantity=(
                    parse_quantity(command.quantity)
                    if command.quantity is not None
                    else None
                ),
                details=command.details,
            )
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return shopping_list_item_details(self._items.update(item))
