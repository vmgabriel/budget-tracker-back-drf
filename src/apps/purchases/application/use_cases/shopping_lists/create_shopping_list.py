"""Shopping list creation use case."""

from apps.purchases.application.commands import CreateShoppingListCommand
from apps.purchases.application.dto import ShoppingListDetails, shopping_list_details
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.parsing import parse_list_priority
from apps.purchases.application.ports.repositories import ShoppingListRepository
from apps.purchases.domain.entities import ShoppingList
from apps.purchases.domain.exceptions import PurchasesDomainError
from apps.purchases.domain.value_objects import UserId
from shared.domain.ports.clock import Clock


class CreateShoppingList:
    """Create a shopping list owned by the requesting user."""

    def __init__(self, shopping_lists: ShoppingListRepository, clock: Clock) -> None:
        self._shopping_lists = shopping_lists
        self._clock = clock

    def execute(self, command: CreateShoppingListCommand) -> ShoppingListDetails:
        priority = parse_list_priority(command.priority)
        try:
            shopping_list = ShoppingList.create(
                user_id=UserId(value=command.user_id),
                name=command.name,
                now=self._clock.now(),
                priority=priority,
            )
        except (PurchasesDomainError, TypeError, ValueError) as error:
            raise InvalidPurchasesInput(str(error)) from error
        return shopping_list_details(self._shopping_lists.save(shopping_list))
