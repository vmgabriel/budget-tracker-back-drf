"""Composition root for the purchases bounded context."""

from dataclasses import dataclass

from apps.purchases.application.use_cases import (
    AddItemToShoppingList,
    AddItemToWishlist,
    AddTagsToItem,
    AddTagsToWishlistItem,
    CreateShoppingList,
    CreateTag,
    DeleteShoppingListItem,
    DeleteWishlistItem,
    GetOrCreateWishlist,
    GetShoppingList,
    GetWishlist,
    ListInactiveShoppingLists,
    ListTags,
    ListUserShoppingLists,
    MarkItemAsPurchased,
    MarkWishlistItemAsPurchased,
    RemoveTagsFromItem,
    RemoveTagsFromWishlistItem,
    RestoreShoppingList,
    SoftDeleteShoppingList,
    UpdateShoppingList,
    UpdateShoppingListItem,
    UpdateWishlist,
    UpdateWishlistItem,
)
from apps.purchases.infrastructure.persistence.repositories import (
    DjangoShoppingListItemRepository,
    DjangoShoppingListRepository,
    DjangoTagRepository,
    DjangoWishlistItemRepository,
    DjangoWishlistRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class PurchasesUseCases:
    """Purchases use cases sharing one set of persistence adapters."""

    create_shopping_list: CreateShoppingList
    get_shopping_list: GetShoppingList
    list_user_shopping_lists: ListUserShoppingLists
    list_inactive_shopping_lists: ListInactiveShoppingLists
    update_shopping_list: UpdateShoppingList
    soft_delete_shopping_list: SoftDeleteShoppingList
    restore_shopping_list: RestoreShoppingList
    add_item_to_shopping_list: AddItemToShoppingList
    update_shopping_list_item: UpdateShoppingListItem
    delete_shopping_list_item: DeleteShoppingListItem
    mark_item_as_purchased: MarkItemAsPurchased
    add_tags_to_item: AddTagsToItem
    remove_tags_from_item: RemoveTagsFromItem
    get_or_create_wishlist: GetOrCreateWishlist
    get_wishlist: GetWishlist
    update_wishlist: UpdateWishlist
    add_item_to_wishlist: AddItemToWishlist
    update_wishlist_item: UpdateWishlistItem
    delete_wishlist_item: DeleteWishlistItem
    mark_wishlist_item_as_purchased: MarkWishlistItemAsPurchased
    add_tags_to_wishlist_item: AddTagsToWishlistItem
    remove_tags_from_wishlist_item: RemoveTagsFromWishlistItem
    list_tags: ListTags
    create_tag: CreateTag


def build_purchases_use_cases() -> PurchasesUseCases:
    """Build purchases use cases with infrastructure dependencies."""
    shopping_lists = DjangoShoppingListRepository()
    shopping_list_items = DjangoShoppingListItemRepository()
    wishlists = DjangoWishlistRepository()
    wishlist_items = DjangoWishlistItemRepository()
    tags = DjangoTagRepository()
    clock = SystemClock()
    return PurchasesUseCases(
        create_shopping_list=CreateShoppingList(shopping_lists, clock),
        get_shopping_list=GetShoppingList(shopping_lists, shopping_list_items),
        list_user_shopping_lists=ListUserShoppingLists(shopping_lists),
        list_inactive_shopping_lists=ListInactiveShoppingLists(shopping_lists),
        update_shopping_list=UpdateShoppingList(shopping_lists),
        soft_delete_shopping_list=SoftDeleteShoppingList(shopping_lists),
        restore_shopping_list=RestoreShoppingList(shopping_lists),
        add_item_to_shopping_list=AddItemToShoppingList(
            shopping_lists, shopping_list_items
        ),
        update_shopping_list_item=UpdateShoppingListItem(
            shopping_lists, shopping_list_items
        ),
        delete_shopping_list_item=DeleteShoppingListItem(
            shopping_lists, shopping_list_items, clock
        ),
        mark_item_as_purchased=MarkItemAsPurchased(
            shopping_lists, shopping_list_items, clock
        ),
        add_tags_to_item=AddTagsToItem(shopping_lists, shopping_list_items, tags),
        remove_tags_from_item=RemoveTagsFromItem(
            shopping_lists, shopping_list_items, tags
        ),
        get_or_create_wishlist=GetOrCreateWishlist(wishlists, wishlist_items, clock),
        get_wishlist=GetWishlist(wishlists, wishlist_items),
        update_wishlist=UpdateWishlist(wishlists),
        add_item_to_wishlist=AddItemToWishlist(wishlists, wishlist_items),
        update_wishlist_item=UpdateWishlistItem(wishlists, wishlist_items),
        delete_wishlist_item=DeleteWishlistItem(wishlists, wishlist_items, clock),
        mark_wishlist_item_as_purchased=MarkWishlistItemAsPurchased(
            wishlists, wishlist_items, clock
        ),
        add_tags_to_wishlist_item=AddTagsToWishlistItem(
            wishlists, wishlist_items, tags
        ),
        remove_tags_from_wishlist_item=RemoveTagsFromWishlistItem(
            wishlists, wishlist_items, tags
        ),
        list_tags=ListTags(tags),
        create_tag=CreateTag(tags),
    )
