"""Persistence ports for the purchases context.

Every method speaks in domain value objects and returns domain entities, so
use cases never see a storage concern. Adapters live under
``purchases/infrastructure``.
"""

from datetime import datetime
from typing import Protocol

from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Tag,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.value_objects import (
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    UserId,
    WishlistId,
    WishlistItemId,
)


class ShoppingListRepository(Protocol):
    """Storage operations required by shopping list use cases."""

    def get_by_id(self, shopping_list_id: ShoppingListId) -> ShoppingList | None:
        """Find a shopping list by its identity."""
        ...

    def get_by_user_id(
        self, user_id: UserId, active_only: bool = True
    ) -> list[ShoppingList]:
        """Return the lists owned by ``user_id``.

        With ``active_only`` the soft-deleted lists are filtered out, which is
        what every default view needs.
        """
        ...

    def save(self, shopping_list: ShoppingList) -> ShoppingList:
        """Persist a new shopping list and return its stored representation."""
        ...

    def update(self, shopping_list: ShoppingList) -> ShoppingList:
        """Persist changes made to an existing shopping list."""
        ...

    def soft_delete(self, shopping_list_id: ShoppingListId) -> None:
        """Hide a shopping list without discarding its items."""
        ...

    def restore(self, shopping_list_id: ShoppingListId) -> None:
        """Bring a soft-deleted shopping list back."""
        ...

    def get_archived_candidates(self, completed_before: datetime) -> list[ShoppingList]:
        """Return active shopping lists completed at or before ``completed_before``.

        These are only candidates: whether one is stale enough to archive
        depends on a per-user delay the repository cannot know.
        """
        ...


class WishlistRepository(Protocol):
    """Storage operations required by wishlist use cases.

    A user owns at most one wishlist; the adapter enforces that with a
    one-to-one relation and reports a race with ``WishlistAlreadyExists``.
    """

    def get_by_id(self, wishlist_id: WishlistId) -> Wishlist | None:
        """Find a wishlist by its identity."""
        ...

    def get_by_user_id(self, user_id: UserId) -> Wishlist | None:
        """Return the single wishlist of ``user_id``, or ``None``."""
        ...

    def save(self, wishlist: Wishlist) -> Wishlist:
        """Persist a new wishlist and return its stored representation."""
        ...

    def update(self, wishlist: Wishlist) -> Wishlist:
        """Persist changes made to an existing wishlist."""
        ...

    def soft_delete(self, wishlist_id: WishlistId) -> None:
        """Hide a wishlist from its owner's default view without discarding it."""
        ...

    def get_archived_candidates(self, completed_before: datetime) -> list[Wishlist]:
        """Return active wishlists completed at or before ``completed_before``.

        These are only candidates: whether one is stale enough to archive
        depends on a per-user delay the repository cannot know.
        """
        ...


class ShoppingListItemRepository(Protocol):
    """Storage operations required by shopping list item use cases."""

    def get_by_list_id(
        self, shopping_list_id: ShoppingListId
    ) -> list[ShoppingListItem]:
        """Return every item belonging to one shopping list."""
        ...

    def get_by_id(self, item_id: ShoppingListItemId) -> ShoppingListItem | None:
        """Find a shopping list item by its identity."""
        ...

    def save(self, item: ShoppingListItem) -> ShoppingListItem:
        """Persist a new shopping list item and return its stored form."""
        ...

    def update(self, item: ShoppingListItem) -> ShoppingListItem:
        """Persist changes made to an existing shopping list item."""
        ...

    def delete(self, item_id: ShoppingListItemId) -> None:
        """Remove a shopping list item and its tag associations."""
        ...


class WishlistItemRepository(Protocol):
    """Storage operations required by wishlist item use cases."""

    def get_by_wishlist_id(self, wishlist_id: WishlistId) -> list[WishlistItem]:
        """Return every item belonging to one wishlist."""
        ...

    def get_by_id(self, item_id: WishlistItemId) -> WishlistItem | None:
        """Find a wishlist item by its identity."""
        ...

    def save(self, item: WishlistItem) -> WishlistItem:
        """Persist a new wishlist item and return its stored representation."""
        ...

    def update(self, item: WishlistItem) -> WishlistItem:
        """Persist changes made to an existing wishlist item."""
        ...

    def delete(self, item_id: WishlistItemId) -> None:
        """Remove a wishlist item and its tag associations."""
        ...


class TagRepository(Protocol):
    """Storage operations required by tag use cases."""

    def get_by_id(self, tag_id: TagId) -> Tag | None:
        """Find a tag by its identity."""
        ...

    def get_by_name_or_slug(self, name_or_slug: str) -> Tag | None:
        """Find a tag by its exact name or by its slug."""
        ...

    def get_or_create(self, name: str) -> Tag:
        """Return the catalogue tag named ``name``, creating it when absent."""
        ...

    def list_all(self) -> list[Tag]:
        """Return every tag in the catalogue, ordered by name."""
        ...
