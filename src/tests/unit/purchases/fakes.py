"""In-memory test doubles for purchases application ports."""

from datetime import UTC, date, datetime
from uuid import uuid4

from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Tag,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.exceptions import WishlistAlreadyExists
from apps.purchases.domain.value_objects import (
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    UserId,
    WishlistId,
    WishlistItemId,
)

FIXED_NOW = datetime(2026, 1, 15, 12, tzinfo=UTC)


class FakeClock:
    """Return a configurable timezone-aware timestamp."""

    def __init__(self, now: datetime = FIXED_NOW) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()


class FakeShoppingListRepository:
    """Store shopping lists in memory."""

    def __init__(self) -> None:
        self.shopping_lists: dict[ShoppingListId, ShoppingList] = {}
        self.soft_deleted: list[ShoppingListId] = []
        self.restored: list[ShoppingListId] = []

    def get_by_id(self, shopping_list_id: ShoppingListId) -> ShoppingList | None:
        return self.shopping_lists.get(shopping_list_id)

    def get_by_user_id(
        self, user_id: UserId, active_only: bool = True
    ) -> list[ShoppingList]:
        return [
            shopping_list
            for shopping_list in self.shopping_lists.values()
            if shopping_list.user_id == user_id
            and (not active_only or shopping_list.is_active)
        ]

    def save(self, shopping_list: ShoppingList) -> ShoppingList:
        if shopping_list.id is None:
            shopping_list.id = ShoppingListId(uuid4())
        self.shopping_lists[shopping_list.id] = shopping_list
        return shopping_list

    def update(self, shopping_list: ShoppingList) -> ShoppingList:
        if shopping_list.id is None:
            raise ValueError("Cannot update an unidentified shopping list.")
        self.shopping_lists[shopping_list.id] = shopping_list
        return shopping_list

    def soft_delete(self, shopping_list_id: ShoppingListId) -> None:
        self.soft_deleted.append(shopping_list_id)
        shopping_list = self.shopping_lists[shopping_list_id]
        shopping_list.soft_delete()

    def restore(self, shopping_list_id: ShoppingListId) -> None:
        self.restored.append(shopping_list_id)
        shopping_list = self.shopping_lists[shopping_list_id]
        shopping_list.restore()


class FakeWishlistRepository:
    """Store wishlists in memory, enforcing one per user."""

    def __init__(self) -> None:
        self.wishlists: dict[WishlistId, Wishlist] = {}

    def get_by_id(self, wishlist_id: WishlistId) -> Wishlist | None:
        return self.wishlists.get(wishlist_id)

    def get_by_user_id(self, user_id: UserId) -> Wishlist | None:
        for wishlist in self.wishlists.values():
            if wishlist.user_id == user_id:
                return wishlist
        return None

    def save(self, wishlist: Wishlist) -> Wishlist:
        existing = self.get_by_user_id(wishlist.user_id)
        if existing is not None and existing.id != wishlist.id:
            raise WishlistAlreadyExists("This user already has a wishlist.")
        if wishlist.id is None:
            wishlist.id = WishlistId(uuid4())
        self.wishlists[wishlist.id] = wishlist
        return wishlist

    def update(self, wishlist: Wishlist) -> Wishlist:
        if wishlist.id is None:
            raise ValueError("Cannot update an unidentified wishlist.")
        self.wishlists[wishlist.id] = wishlist
        return wishlist


class FakeShoppingListItemRepository:
    """Store shopping list items in memory."""

    def __init__(self) -> None:
        self.items: dict[ShoppingListItemId, ShoppingListItem] = {}

    def get_by_list_id(
        self, shopping_list_id: ShoppingListId
    ) -> list[ShoppingListItem]:
        return [
            item
            for item in self.items.values()
            if item.shopping_list_id == shopping_list_id
        ]

    def get_by_id(self, item_id: ShoppingListItemId) -> ShoppingListItem | None:
        return self.items.get(item_id)

    def save(self, item: ShoppingListItem) -> ShoppingListItem:
        if item.id is None:
            item.id = ShoppingListItemId(uuid4())
        self.items[item.id] = item
        return item

    def update(self, item: ShoppingListItem) -> ShoppingListItem:
        if item.id is None:
            raise ValueError("Cannot update an unidentified shopping list item.")
        self.items[item.id] = item
        return item

    def delete(self, item_id: ShoppingListItemId) -> None:
        del self.items[item_id]


class FakeWishlistItemRepository:
    """Store wishlist items in memory."""

    def __init__(self) -> None:
        self.items: dict[WishlistItemId, WishlistItem] = {}

    def get_by_wishlist_id(self, wishlist_id: WishlistId) -> list[WishlistItem]:
        return [item for item in self.items.values() if item.wishlist_id == wishlist_id]

    def get_by_id(self, item_id: WishlistItemId) -> WishlistItem | None:
        return self.items.get(item_id)

    def save(self, item: WishlistItem) -> WishlistItem:
        if item.id is None:
            item.id = WishlistItemId(uuid4())
        self.items[item.id] = item
        return item

    def update(self, item: WishlistItem) -> WishlistItem:
        if item.id is None:
            raise ValueError("Cannot update an unidentified wishlist item.")
        self.items[item.id] = item
        return item

    def delete(self, item_id: WishlistItemId) -> None:
        del self.items[item_id]


class FakeTagRepository:
    """Store the tag catalogue in memory."""

    def __init__(self) -> None:
        self.tags: dict[TagId, Tag] = {}

    def get_by_id(self, tag_id: TagId) -> Tag | None:
        return self.tags.get(tag_id)

    def get_by_name_or_slug(self, name_or_slug: str) -> Tag | None:
        for tag in self.tags.values():
            if tag.matches(name_or_slug):
                return tag
        return None

    def get_or_create(self, name: str) -> Tag:
        existing = self.get_by_name_or_slug(name)
        if existing is not None:
            return existing
        tag = Tag.create(name=name)
        tag.id = TagId(uuid4())
        self.tags[tag.id] = tag
        return tag

    def list_all(self) -> list[Tag]:
        return sorted(self.tags.values(), key=lambda tag: tag.name)
