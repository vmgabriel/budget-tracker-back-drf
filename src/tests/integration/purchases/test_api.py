"""Owner-scoped purchases HTTP interface tests using JWT authentication."""

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.purchases.domain.value_objects import ItemStatus, ListPriority
from apps.purchases.infrastructure.persistence.models import (
    ShoppingListItemModel,
    ShoppingListModel,
    WishlistItemModel,
    WishlistModel,
)
from tests.factories import (
    ShoppingListFactory,
    ShoppingListItemFactory,
    UserFactory,
    WishlistFactory,
    WishlistItemFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _client(user: Any, jwt_token_factory: Any) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt_token_factory(user)}")
    return client


def _make_list(
    client: APIClient, name: str = "Groceries", priority: str = "medium"
) -> str:
    response = client.post(
        reverse("api_v1:purchases:shopping-list-list"),
        {"name": name, "priority": priority},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return str(response.data["id"])


def _add_item(client: APIClient, list_id: str, name: str = "Milk", **extra: Any) -> str:
    response = client.post(
        reverse("api_v1:purchases:shopping-list-add-item", args=[list_id]),
        {"name": name, **extra},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return str(response.data["items"][-1]["id"])


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "route",
    [
        "api_v1:purchases:shopping-list-list",
        "api_v1:purchases:shopping-list-list-inactive",
        "api_v1:purchases:wishlist",
        "api_v1:purchases:tag-list",
    ],
)
def test_purchases_endpoints_require_authentication(route: str) -> None:
    response = APIClient().get(reverse(route))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Shopping lists: CRUD
# ---------------------------------------------------------------------------


def test_create_list_defaults_to_medium_priority(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-list"),
        {"name": "  Weekly groceries "},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Weekly groceries"
    assert response.data["priority"] == ListPriority.MEDIUM.value
    assert response.data["status"] == ItemStatus.PENDING.value
    assert response.data["is_active"] is True
    assert response.data["items"] == []


def test_create_list_rejects_a_blank_name(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-list"),
        {"name": "   "},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data


def test_create_list_rejects_an_unknown_priority(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-list"),
        {"name": "Groceries", "priority": "urgent"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_list_returns_only_the_callers_active_lists(jwt_token_factory: Any) -> None:
    user: Any = UserFactory()
    client = _client(user, jwt_token_factory)
    kept = _make_list(client, name="Kept")
    removed = _make_list(client, name="Removed")
    ShoppingListFactory(user=UserFactory(), name="Somebody else")

    listed = client.get(reverse("api_v1:purchases:shopping-list-list"))
    assert listed.status_code == status.HTTP_200_OK
    # Both of the caller's lists are active; the other user's is not present.
    assert {entry["id"] for entry in listed.data} == {kept, removed}

    deleted = client.delete(
        reverse("api_v1:purchases:shopping-list-detail", args=[removed])
    )
    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.data["is_active"] is False

    listed = client.get(reverse("api_v1:purchases:shopping-list-list"))
    assert [entry["id"] for entry in listed.data] == [kept]

    inactive = client.get(reverse("api_v1:purchases:shopping-list-list-inactive"))
    assert [entry["id"] for entry in inactive.data] == [removed]


def test_delete_is_a_soft_delete_that_keeps_the_items(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    _add_item(client, list_id, name="Milk")

    deleted = client.delete(
        reverse("api_v1:purchases:shopping-list-detail", args=[list_id])
    )

    assert deleted.status_code == status.HTTP_200_OK
    assert deleted.data["is_active"] is False
    # The row survives: this is a soft delete, not a discard.
    assert ShoppingListModel.objects.filter(pk=list_id).exists() is True
    assert ShoppingListModel.objects.get(pk=list_id).is_active is False


def test_restore_brings_a_soft_deleted_list_back(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    client.delete(reverse("api_v1:purchases:shopping-list-detail", args=[list_id]))

    restored = client.post(
        reverse("api_v1:purchases:shopping-list-restore", args=[list_id])
    )

    assert restored.status_code == status.HTTP_200_OK
    assert restored.data["is_active"] is True
    assert ShoppingListModel.objects.get(pk=list_id).is_active is True


def test_partial_update_changes_the_name_and_priority(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)

    updated = client.patch(
        reverse("api_v1:purchases:shopping-list-detail", args=[list_id]),
        {"name": "Household", "priority": "high"},
        format="json",
    )

    assert updated.status_code == status.HTTP_200_OK
    assert updated.data["name"] == "Household"
    assert updated.data["priority"] == ListPriority.HIGH.value


def test_partial_update_with_an_empty_body_is_rejected(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)

    response = client.patch(
        reverse("api_v1:purchases:shopping-list-detail", args=[list_id]),
        {},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Owner scoping
# ---------------------------------------------------------------------------


def test_a_foreign_list_is_invisible(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    stranger: Any = UserFactory()
    shopping_list: Any = ShoppingListFactory(user=owner)
    client = _client(stranger, jwt_token_factory)

    for route, method in (
        ("api_v1:purchases:shopping-list-detail", "get"),
        ("api_v1:purchases:shopping-list-detail", "delete"),
        ("api_v1:purchases:shopping-list-restore", "post"),
    ):
        response = getattr(client, method)(reverse(route, args=[str(shopping_list.pk)]))
        assert response.status_code == status.HTTP_404_NOT_FOUND, route

    update = client.patch(
        reverse("api_v1:purchases:shopping-list-detail", args=[str(shopping_list.pk)]),
        {"name": "Mine now"},
        format="json",
    )
    assert update.status_code == status.HTTP_404_NOT_FOUND
    assert ShoppingListModel.objects.get(pk=shopping_list.pk).name == shopping_list.name


def test_a_stranger_cannot_add_an_item_to_a_foreign_list(
    jwt_token_factory: Any,
) -> None:
    shopping_list: Any = ShoppingListFactory(user=UserFactory())
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse(
            "api_v1:purchases:shopping-list-add-item", args=[str(shopping_list.pk)]
        ),
        {"name": "Milk"},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_stranger_cannot_touch_a_foreign_item(jwt_token_factory: Any) -> None:
    owner: Any = UserFactory()
    shopping_list: Any = ShoppingListFactory(user=owner)
    item: Any = ShoppingListItemFactory(shopping_list=shopping_list, name="Milk")
    stranger_client = _client(UserFactory(), jwt_token_factory)
    list_id = str(shopping_list.pk)

    patch = stranger_client.patch(
        reverse(
            "api_v1:purchases:shopping-list-item-detail", args=[list_id, str(item.pk)]
        ),
        {"name": "Poison"},
        format="json",
    )
    delete = stranger_client.delete(
        reverse(
            "api_v1:purchases:shopping-list-item-detail", args=[list_id, str(item.pk)]
        )
    )
    purchased = stranger_client.post(
        reverse(
            "api_v1:purchases:shopping-list-item-mark-purchased",
            args=[list_id, str(item.pk)],
        )
    )
    tagged = stranger_client.post(
        reverse(
            "api_v1:purchases:shopping-list-item-tags", args=[list_id, str(item.pk)]
        ),
        {"tag_names": ["Dairy"]},
        format="json",
    )

    for response in (patch, delete, purchased, tagged):
        assert response.status_code == status.HTTP_404_NOT_FOUND


def test_an_item_from_another_list_is_rejected_in_a_nested_url(
    jwt_token_factory: Any,
) -> None:
    """The addressed list must contain the addressed item.

    Owner scoping alone is not enough: without this the URL
    ``/lists/A/items/B/`` would happily mutate B even when B lives in the
    caller's own list C.
    """
    user: Any = UserFactory()
    client = _client(user, jwt_token_factory)
    first: Any = ShoppingListFactory(user=user)
    second: Any = ShoppingListFactory(user=user)
    foreign_item: Any = ShoppingListItemFactory(shopping_list=second, name="Milk")

    response = client.patch(
        reverse(
            "api_v1:purchases:shopping-list-item-detail",
            args=[str(first.pk), str(foreign_item.pk)],
        ),
        {"name": "Poison"},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert ShoppingListItemModel.objects.get(pk=foreign_item.pk).name == "Milk"


def test_an_unknown_list_is_a_not_found(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.get(
        reverse("api_v1:purchases:shopping-list-detail", args=[str(uuid4())])
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def test_add_item_defaults_to_quantity_one(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-add-item", args=[list_id]),
        {"name": "Bread"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["items"][-1]["quantity"] == 1
    assert response.data["items"][-1]["status"] == ItemStatus.PENDING.value


def test_add_item_rejects_a_non_positive_quantity(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-add-item", args=[list_id]),
        {"name": "Bread", "quantity": 0},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_update_item_changes_its_fields(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)

    response = client.patch(
        reverse("api_v1:purchases:shopping-list-item-detail", args=[list_id, item_id]),
        {"quantity": 4, "details": "one liter"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["quantity"] == 4
    assert response.data["details"] == "one liter"


def test_delete_item_removes_it_and_reopens_the_list(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)
    client.post(
        reverse(
            "api_v1:purchases:shopping-list-item-mark-purchased",
            args=[list_id, item_id],
        )
    )

    response = client.delete(
        reverse("api_v1:purchases:shopping-list-item-detail", args=[list_id, item_id])
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["items"] == []
    assert response.data["status"] == ItemStatus.PENDING.value
    assert response.data["completed_at"] is None


def test_marking_the_last_item_purchased_completes_the_list(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    first = _add_item(client, list_id, name="Milk")
    second = _add_item(client, list_id, name="Bread")

    partial = client.post(
        reverse(
            "api_v1:purchases:shopping-list-item-mark-purchased",
            args=[list_id, first],
        )
    )
    assert partial.data["status"] == ItemStatus.PENDING.value
    assert partial.data["completed_at"] is None

    completed = client.post(
        reverse(
            "api_v1:purchases:shopping-list-item-mark-purchased",
            args=[list_id, second],
        )
    )
    assert completed.data["status"] == ItemStatus.PURCHASED.value
    assert completed.data["completed_at"] is not None


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_tags_are_created_and_attached_to_an_item(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)

    tagged = client.post(
        reverse("api_v1:purchases:shopping-list-item-tags", args=[list_id, item_id]),
        {"tag_names": ["Dairy", "Urgent"]},
        format="json",
    )

    assert tagged.status_code == status.HTTP_200_OK
    assert {tag["name"] for tag in tagged.data["tags"]} == {"Dairy", "Urgent"}

    catalogue = client.get(reverse("api_v1:purchases:tag-list"))
    assert {tag["name"] for tag in catalogue.data} == {"Dairy", "Urgent"}


def test_attaching_the_same_tag_twice_is_idempotent(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)
    route = reverse("api_v1:purchases:shopping-list-item-tags", args=[list_id, item_id])

    first = client.post(route, {"tag_names": ["Dairy"]}, format="json")
    second = client.post(route, {"tag_names": ["dairy"]}, format="json")

    assert len(second.data["tags"]) == len(first.data["tags"]) == 1


def test_removing_a_tag_detaches_it_but_keeps_the_catalogue_entry(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)
    route = reverse("api_v1:purchases:shopping-list-item-tags", args=[list_id, item_id])
    tagged = client.post(route, {"tag_names": ["Dairy"]}, format="json")

    removed = client.delete(
        route, {"tag_ids": [tagged.data["tags"][0]["id"]]}, format="json"
    )

    assert removed.status_code == status.HTTP_200_OK
    assert removed.data["tags"] == []
    assert len(client.get(reverse("api_v1:purchases:tag-list")).data) == 1


def test_removing_an_unknown_tag_is_a_not_found(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)

    response = client.delete(
        reverse("api_v1:purchases:shopping-list-item-tags", args=[list_id, item_id]),
        {"tag_ids": [str(uuid4())]},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_adding_no_tags_is_rejected(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    list_id = _make_list(client)
    item_id = _add_item(client, list_id)

    response = client.post(
        reverse("api_v1:purchases:shopping-list-item-tags", args=[list_id, item_id]),
        {"tag_names": []},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_create_tag_is_idempotent_and_returns_201(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    route = reverse("api_v1:purchases:tag-list")

    first = client.post(route, {"name": "Dairy"}, format="json")
    second = client.post(route, {"name": "  dairy  "}, format="json")

    assert first.status_code == status.HTTP_201_CREATED
    assert first.data["slug"] == "dairy"
    assert second.data["id"] == first.data["id"]
    assert len(client.get(route).data) == 1


def test_tag_catalogue_is_shared_across_users(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    client.post(reverse("api_v1:purchases:tag-list"), {"name": "Dairy"}, format="json")

    other = _client(UserFactory(), jwt_token_factory).get(
        reverse("api_v1:purchases:tag-list")
    )

    assert [tag["name"] for tag in other.data] == ["Dairy"]


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------


def test_first_wishlist_access_creates_the_single_list(jwt_token_factory: Any) -> None:
    user: Any = UserFactory()
    client = _client(user, jwt_token_factory)

    first = client.get(reverse("api_v1:purchases:wishlist"))
    second = client.get(reverse("api_v1:purchases:wishlist"))

    assert first.status_code == status.HTTP_200_OK
    assert first.data["name"] == "My Wishlist"
    assert second.data["id"] == first.data["id"]
    assert WishlistModel.objects.filter(user=user).count() == 1


def test_each_user_gets_their_own_wishlist(jwt_token_factory: Any) -> None:
    first = _client(UserFactory(), jwt_token_factory).get(
        reverse("api_v1:purchases:wishlist")
    )
    second = _client(UserFactory(), jwt_token_factory).get(
        reverse("api_v1:purchases:wishlist")
    )

    assert first.data["id"] != second.data["id"]


def test_wishlist_can_be_renamed(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.patch(
        reverse("api_v1:purchases:wishlist"), {"name": "Holiday gifts"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Holiday gifts"


def test_add_wishlist_item_keeps_link_price_and_priority(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:wishlist-add-item"),
        {
            "name": "Espresso machine",
            "link": "https://example.com/machine",
            "description": "For the kitchen",
            "estimated_price": "399.90",
            "priority": "must_have",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    item = response.data["items"][-1]
    assert item["link"] == "https://example.com/machine"
    assert Decimal(item["estimated_price"]) == Decimal("399.90")
    assert item["priority"] == "must_have"


def test_add_wishlist_item_rejects_a_malformed_link(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:wishlist-add-item"),
        {"name": "Lamp", "link": "not-a-url"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_add_wishlist_item_rejects_a_negative_price(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)

    response = client.post(
        reverse("api_v1:purchases:wishlist-add-item"),
        {"name": "Lamp", "estimated_price": "-1.00"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_wishlist_items_are_owner_scoped(jwt_token_factory: Any) -> None:
    """A real item owned by somebody else must be invisible, not just unknown."""
    owner: Any = UserFactory()
    wishlist: Any = WishlistFactory(user=owner)
    item: Any = WishlistItemFactory(wishlist=wishlist, name="Lamp")
    stranger = _client(UserFactory(), jwt_token_factory)
    item_id = str(item.pk)

    patch = stranger.patch(
        reverse("api_v1:purchases:wishlist-item-detail", args=[item_id]),
        {"name": "Poison"},
        format="json",
    )
    delete = stranger.delete(
        reverse("api_v1:purchases:wishlist-item-detail", args=[item_id])
    )
    purchased = stranger.post(
        reverse("api_v1:purchases:wishlist-item-mark-purchased", args=[item_id])
    )
    tagged = stranger.post(
        reverse("api_v1:purchases:wishlist-item-tags", args=[item_id]),
        {"tag_names": ["Home"]},
        format="json",
    )

    for response in (patch, delete, purchased, tagged):
        assert response.status_code == status.HTTP_404_NOT_FOUND
    assert WishlistItemModel.objects.get(pk=item.pk).name == "Lamp"


def test_marking_the_last_wishlist_item_purchased_completes_it(
    jwt_token_factory: Any,
) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = client.post(
        reverse("api_v1:purchases:wishlist-add-item"), {"name": "Lamp"}, format="json"
    )
    first = str(created.data["items"][-1]["id"])
    second = client.post(
        reverse("api_v1:purchases:wishlist-add-item"), {"name": "Rug"}, format="json"
    )
    second_id = str(second.data["items"][-1]["id"])

    partial = client.post(
        reverse("api_v1:purchases:wishlist-item-mark-purchased", args=[first])
    )
    assert partial.data["status"] == ItemStatus.PENDING.value

    completed = client.post(
        reverse("api_v1:purchases:wishlist-item-mark-purchased", args=[second_id])
    )
    assert completed.data["status"] == ItemStatus.PURCHASED.value
    assert completed.data["completed_at"] is not None


def test_wishlist_item_tags_are_managed(jwt_token_factory: Any) -> None:
    client = _client(UserFactory(), jwt_token_factory)
    created = client.post(
        reverse("api_v1:purchases:wishlist-add-item"), {"name": "Lamp"}, format="json"
    )
    item_id = str(created.data["items"][-1]["id"])
    route = reverse("api_v1:purchases:wishlist-item-tags", args=[item_id])

    tagged = client.post(route, {"tag_names": ["Home", "Gift"]}, format="json")
    assert {tag["name"] for tag in tagged.data["tags"]} == {"Home", "Gift"}

    removed = client.delete(
        route, {"tag_ids": [tagged.data["tags"][0]["id"]]}, format="json"
    )
    assert len(removed.data["tags"]) == 1
