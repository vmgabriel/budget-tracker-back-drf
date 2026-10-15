"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.purchases.infrastructure.persistence.models import (
    ShoppingListItemModel,
    ShoppingListModel,
    TagModel,
    WishlistItemModel,
    WishlistModel,
)

__all__ = (
    "ShoppingListItemModel",
    "ShoppingListModel",
    "TagModel",
    "WishlistItemModel",
    "WishlistModel",
)
