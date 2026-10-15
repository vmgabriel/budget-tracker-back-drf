"""URL routes for the purchases bounded context."""

from django.urls import path

from apps.purchases.interfaces.views import (
    InactiveShoppingListListView,
    RestoreShoppingListView,
    ShoppingListAddItemView,
    ShoppingListDetailView,
    ShoppingListItemDetailView,
    ShoppingListItemMarkPurchasedView,
    ShoppingListItemTagsView,
    ShoppingListListView,
    TagListView,
    WishlistAddItemView,
    WishlistItemDetailView,
    WishlistItemMarkPurchasedView,
    WishlistItemTagsView,
    WishlistView,
)

app_name = "purchases"

urlpatterns = [
    # Shopping lists
    path("shopping-lists/", ShoppingListListView.as_view(), name="shopping-list-list"),
    path(
        "shopping-lists/inactive/",
        InactiveShoppingListListView.as_view(),
        name="shopping-list-list-inactive",
    ),
    path(
        "shopping-lists/<uuid:pk>/",
        ShoppingListDetailView.as_view(),
        name="shopping-list-detail",
    ),
    path(
        "shopping-lists/<uuid:pk>/restore/",
        RestoreShoppingListView.as_view(),
        name="shopping-list-restore",
    ),
    path(
        "shopping-lists/<uuid:pk>/add-item/",
        ShoppingListAddItemView.as_view(),
        name="shopping-list-add-item",
    ),
    path(
        "shopping-lists/<uuid:pk>/items/<uuid:item_id>/",
        ShoppingListItemDetailView.as_view(),
        name="shopping-list-item-detail",
    ),
    path(
        "shopping-lists/<uuid:pk>/items/<uuid:item_id>/mark-purchased/",
        ShoppingListItemMarkPurchasedView.as_view(),
        name="shopping-list-item-mark-purchased",
    ),
    path(
        "shopping-lists/<uuid:pk>/items/<uuid:item_id>/tags/",
        ShoppingListItemTagsView.as_view(),
        name="shopping-list-item-tags",
    ),
    # Wishlist
    path("wishlist/", WishlistView.as_view(), name="wishlist"),
    path("wishlist/add-item/", WishlistAddItemView.as_view(), name="wishlist-add-item"),
    path(
        "wishlist/items/<uuid:item_id>/",
        WishlistItemDetailView.as_view(),
        name="wishlist-item-detail",
    ),
    path(
        "wishlist/items/<uuid:item_id>/mark-purchased/",
        WishlistItemMarkPurchasedView.as_view(),
        name="wishlist-item-mark-purchased",
    ),
    path(
        "wishlist/items/<uuid:item_id>/tags/",
        WishlistItemTagsView.as_view(),
        name="wishlist-item-tags",
    ),
    # Tags
    path("tags/", TagListView.as_view(), name="tag-list"),
]
