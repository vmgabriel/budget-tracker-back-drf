"""Shopping list use cases."""

from apps.purchases.application.use_cases.shopping_lists.add_item_to_shopping_list import (
    AddItemToShoppingList,
)
from apps.purchases.application.use_cases.shopping_lists.create_shopping_list import (
    CreateShoppingList,
)
from apps.purchases.application.use_cases.shopping_lists.delete_shopping_list_item import (
    DeleteShoppingListItem,
)
from apps.purchases.application.use_cases.shopping_lists.get_shopping_list import (
    GetShoppingList,
)
from apps.purchases.application.use_cases.shopping_lists.list_shopping_lists import (
    ListInactiveShoppingLists,
    ListUserShoppingLists,
)
from apps.purchases.application.use_cases.shopping_lists.mark_item_as_purchased import (
    MarkItemAsPurchased,
)
from apps.purchases.application.use_cases.shopping_lists.set_shopping_list_activity import (
    RestoreShoppingList,
    SoftDeleteShoppingList,
)
from apps.purchases.application.use_cases.shopping_lists.shopping_list_item_tags import (
    AddTagsToItem,
    RemoveTagsFromItem,
)
from apps.purchases.application.use_cases.shopping_lists.update_shopping_list import (
    UpdateShoppingList,
)
from apps.purchases.application.use_cases.shopping_lists.update_shopping_list_item import (
    UpdateShoppingListItem,
)

__all__ = (
    "AddItemToShoppingList",
    "AddTagsToItem",
    "CreateShoppingList",
    "DeleteShoppingListItem",
    "GetShoppingList",
    "ListInactiveShoppingLists",
    "ListUserShoppingLists",
    "MarkItemAsPurchased",
    "RemoveTagsFromItem",
    "RestoreShoppingList",
    "SoftDeleteShoppingList",
    "UpdateShoppingList",
    "UpdateShoppingListItem",
)
