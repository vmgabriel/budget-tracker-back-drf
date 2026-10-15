"""Purchases entity and business-rule tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Tag,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.exceptions import (
    ShoppingListItemNotFound,
    WishlistItemNotFound,
)
from apps.purchases.domain.value_objects import (
    ArchiveDelay,
    EstimatedPrice,
    ItemStatus,
    Link,
    ListPriority,
    Quantity,
    ShoppingListId,
    ShoppingListItemId,
    UserId,
    WishlistId,
    WishlistItemId,
    WishlistPriority,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _list(*items: ShoppingListItem) -> ShoppingList:
    shopping_list = ShoppingList.create(
        user_id=UserId(value=uuid4()),
        name="  Weekly   groceries ",
        now=NOW,
        priority=ListPriority.HIGH,
    )
    for item in items:
        shopping_list.add_item(item)
    return shopping_list


def _item(
    name: str = "Milk",
    *,
    status: ItemStatus = ItemStatus.PENDING,
    list_id: ShoppingListId | None = None,
) -> ShoppingListItem:
    return ShoppingListItem.create(
        shopping_list_id=list_id or ShoppingListId(value=uuid4()),
        name=name,
        quantity=Quantity(2),
        status=status,
    )


# --------------------------------------------------------------------------
# Tag
# --------------------------------------------------------------------------


def test_tag_slug_is_derived_from_the_name() -> None:
    tag = Tag.create(name="  Dairy & Eggs ")

    assert tag.name == "Dairy & Eggs"
    assert tag.slug == "dairy-eggs"


def test_tag_rename_regenerates_the_slug() -> None:
    tag = Tag.create(name="Produce")
    tag.rename("Fresh Produce")

    assert (tag.name, tag.slug) == ("Fresh Produce", "fresh-produce")


def test_tag_matches_by_name_or_slug() -> None:
    tag = Tag.create(name="Dairy & Eggs")

    assert tag.matches("Dairy & Eggs")
    assert tag.matches("dairy-eggs")
    assert not tag.matches("bakery")


def test_tag_rejects_blank_or_punctuation_only_names() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        Tag.create(name="   ")
    with pytest.raises(ValueError, match="alphanumeric"):
        Tag.create(name="***")
    with pytest.raises(ValueError, match="cannot exceed"):
        Tag.create(name="a" * 51)


# --------------------------------------------------------------------------
# ShoppingList
# --------------------------------------------------------------------------


def test_create_normalizes_the_name_and_defaults_to_pending() -> None:
    shopping_list = _list()

    assert shopping_list.name == "Weekly groceries"
    assert shopping_list.priority is ListPriority.HIGH
    assert shopping_list.status is ItemStatus.PENDING
    assert shopping_list.is_active is True
    assert shopping_list.completed_at is None
    assert shopping_list.created_at == NOW
    assert shopping_list.id is None


def test_create_requires_a_user_id_and_an_aware_timestamp() -> None:
    with pytest.raises(TypeError, match="UserId"):
        ShoppingList.create(user_id=uuid4(), name="List", now=NOW)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="timezone-aware"):
        ShoppingList.create(
            user_id=UserId(value=uuid4()),
            name="List",
            now=datetime(2026, 3, 1, 12, 0),
        )


def test_create_rejects_an_unknown_priority() -> None:
    with pytest.raises(ValueError, match="priority is invalid"):
        ShoppingList.create(
            user_id=UserId(value=uuid4()),
            name="List",
            now=NOW,
            priority="urgent",  # type: ignore[arg-type]
        )


def test_empty_list_is_never_completed() -> None:
    assert _list().is_completed() is False


def test_list_completes_only_when_every_item_is_purchased() -> None:
    shopping_list = _list(_item(status=ItemStatus.PURCHASED), _item(name="Bread"))
    assert shopping_list.is_completed() is False

    shopping_list.items[1].mark_as_purchased()
    assert shopping_list.is_completed() is True


def test_mark_as_completed_stamps_the_completion_date() -> None:
    shopping_list = _list(_item())
    later = NOW + timedelta(hours=2)

    shopping_list.mark_as_completed(now=later)

    assert shopping_list.status is ItemStatus.PURCHASED
    assert shopping_list.completed_at == later


def test_refresh_status_completes_and_reopens_the_list() -> None:
    shopping_list = _list(_item(), _item(name="Bread"))
    completed_at = NOW + timedelta(hours=1)

    assert shopping_list.refresh_status(now=completed_at) is False

    shopping_list.items[0].mark_as_purchased()
    shopping_list.items[1].mark_as_purchased()
    assert shopping_list.refresh_status(now=completed_at) is True
    assert shopping_list.status is ItemStatus.PURCHASED
    assert shopping_list.completed_at == completed_at

    shopping_list.items[1].mark_as_pending()
    assert shopping_list.refresh_status(now=completed_at) is True
    assert shopping_list.status is ItemStatus.PENDING
    assert shopping_list.completed_at is None
    assert shopping_list.refresh_status(now=completed_at) is False


def test_should_archive_requires_completion_and_a_stale_date() -> None:
    completed = _list(_item(status=ItemStatus.PURCHASED))
    completed.mark_as_completed(now=NOW)

    assert completed.should_archive(NOW + timedelta(days=7)) is False
    assert completed.should_archive(NOW + timedelta(days=7, hours=1)) is True
    assert completed.should_archive(NOW + timedelta(days=365)) is True


def test_should_archive_is_false_while_the_list_is_pending() -> None:
    shopping_list = _list(_item(status=ItemStatus.PURCHASED))

    assert shopping_list.should_archive(NOW + timedelta(days=365)) is False


def test_should_archive_honours_a_custom_delay() -> None:
    completed = _list(_item(status=ItemStatus.PURCHASED))
    completed.mark_as_completed(now=NOW)
    reference = NOW + timedelta(days=3)

    assert completed.should_archive(reference) is False
    assert completed.should_archive(reference, ArchiveDelay(Decimal("2.5"))) is True
    assert completed.should_archive(reference, 1) is True


def test_soft_delete_and_restore_flip_the_active_flag() -> None:
    shopping_list = _list()
    shopping_list.soft_delete()

    assert shopping_list.is_active is False

    shopping_list.restore()
    assert shopping_list.is_active is True


def test_add_item_rejects_an_item_from_another_list() -> None:
    shopping_list = _list()
    shopping_list.id = ShoppingListId(value=uuid4())
    foreign = _item(list_id=ShoppingListId(value=uuid4()))

    with pytest.raises(ValueError, match="different shopping list"):
        shopping_list.add_item(foreign)


def test_get_and_remove_item_use_the_list_as_the_boundary() -> None:
    shopping_list = _list()
    item = _item()
    item.id = ShoppingListItemId(value=uuid4())
    shopping_list.add_item(item)

    assert shopping_list.get_item(item.id.value) is item

    shopping_list.remove_item(item.id.value)
    assert shopping_list.items == []
    with pytest.raises(ShoppingListItemNotFound):
        shopping_list.get_item(item.id.value)
    with pytest.raises(ShoppingListItemNotFound):
        shopping_list.remove_item(item.id.value)


# --------------------------------------------------------------------------
# ShoppingListItem
# --------------------------------------------------------------------------


def test_item_update_applies_a_partial_replacement() -> None:
    item = _item("  Whole   milk ")
    item.update(quantity=Quantity(5), details="  one liter  ")

    assert item.name == "Whole milk"
    assert int(item.quantity) == 5
    assert item.details == "one liter"


def test_item_update_validates_status_and_quantity_types() -> None:
    item = _item()

    with pytest.raises(ValueError, match="status is invalid"):
        item.update(status="bought")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Quantity"):
        item.update(quantity=3)  # type: ignore[arg-type]


def test_item_tag_association_is_idempotent() -> None:
    item = _item()
    dairy = Tag.create(name="Dairy")

    assert item.add_tags([dairy, Tag.create(name="dairy")]) == 1
    assert item.add_tags([dairy]) == 0
    assert item.remove_tags([Tag.create(name="Dairy")]) == 1
    assert item.tags == []
    assert item.remove_tags([dairy]) == 0


# --------------------------------------------------------------------------
# Wishlist
# --------------------------------------------------------------------------


def test_wishlist_defaults_to_my_wishlist() -> None:
    wishlist = Wishlist.create(user_id=UserId(value=uuid4()), now=NOW)

    assert wishlist.name == "My Wishlist"
    assert wishlist.status is ItemStatus.PENDING
    assert wishlist.is_active is True


def _wishlist_item(status: ItemStatus = ItemStatus.PENDING) -> WishlistItem:
    return WishlistItem.create(
        wishlist_id=WishlistId(value=uuid4()),
        name="Espresso machine",
        link=Link("https://example.com/machine"),
        estimated_price=EstimatedPrice(Decimal("399.90")),
        priority=WishlistPriority.MUST_HAVE,
        status=status,
    )


def test_wishlist_shares_the_archival_rules() -> None:
    wishlist = Wishlist.create(user_id=UserId(value=uuid4()), now=NOW)
    wishlist.add_item(_wishlist_item(status=ItemStatus.PURCHASED))
    wishlist.refresh_status(now=NOW)

    assert wishlist.is_completed() is True
    assert wishlist.should_archive(NOW + timedelta(days=8)) is True

    wishlist.soft_delete()
    assert wishlist.is_active is False


def test_wishlist_item_keeps_its_link_and_price() -> None:
    item = _wishlist_item()

    assert str(item.link) == "https://example.com/machine"
    assert item.estimated_price is not None
    assert item.estimated_price.amount == Decimal("399.90")
    assert item.priority is WishlistPriority.MUST_HAVE


def test_wishlist_item_rejects_a_bad_estimated_price() -> None:
    with pytest.raises(TypeError, match="EstimatedPrice"):
        WishlistItem.create(
            wishlist_id=WishlistId(value=uuid4()),
            name="Item",
            estimated_price=Decimal("10"),  # type: ignore[arg-type]
        )


def test_wishlist_item_boundaries_use_wishlist_item_not_found() -> None:
    wishlist = Wishlist.create(user_id=UserId(value=uuid4()), now=NOW)
    item = _wishlist_item()
    item.id = WishlistItemId(value=uuid4())
    wishlist.add_item(item)
    wishlist.remove_item(item.id.value)

    with pytest.raises(WishlistItemNotFound):
        wishlist.get_item(item.id.value)
