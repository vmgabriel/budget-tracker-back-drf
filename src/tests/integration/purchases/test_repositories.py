"""Repository round-trip tests for the purchases adapters."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.exceptions import (
    ShoppingListItemNotFound,
    ShoppingListNotFound,
    WishlistAlreadyExists,
)
from apps.purchases.domain.value_objects import (
    EstimatedPrice,
    ItemStatus,
    Link,
    ListPriority,
    Quantity,
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    UserId,
    WishlistId,
    WishlistItemId,
    WishlistPriority,
)
from apps.purchases.infrastructure.persistence.models import (
    ShoppingListModel,
    TagModel,
    WishlistItemModel,
    WishlistModel,
)
from apps.purchases.infrastructure.persistence.repositories import (
    DjangoShoppingListItemRepository,
    DjangoShoppingListRepository,
    DjangoTagRepository,
    DjangoWishlistItemRepository,
    DjangoWishlistRepository,
)
from tests.factories import ShoppingListFactory, UserFactory, WishlistFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)


def _present[T](value: T | None) -> T:
    """Narrow an Optional repository return that the test expects to exist."""
    assert value is not None
    return value


def _user_id() -> UserId:
    """Return a ``UserId`` for a freshly persisted user."""
    user: Any = UserFactory()
    return UserId(value=user.pk)


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_get_or_create_derives_the_slug_from_the_name() -> None:
    repository = DjangoTagRepository()

    tag = repository.get_or_create("Fresh Produce")

    assert (tag.name, tag.slug) == ("Fresh Produce", "fresh-produce")
    assert _present(repository.get_by_id(TagId(_present(tag.id).value))).name == (
        "Fresh Produce"
    )


def test_get_or_create_is_idempotent_across_case_and_spacing() -> None:
    repository = DjangoTagRepository()

    first = repository.get_or_create("Dairy")
    second = repository.get_or_create("  dairy  ")

    assert first.id == second.id
    assert TagModel.objects.count() == 1


def test_get_by_name_or_slug_finds_both_forms() -> None:
    repository = DjangoTagRepository()
    created = repository.get_or_create("Fresh Produce")
    tag_id = _present(created.id)

    assert _present(repository.get_by_name_or_slug("Fresh Produce")).id == tag_id
    assert _present(repository.get_by_name_or_slug("fresh-produce")).id == tag_id
    assert repository.get_by_name_or_slug("unknown") is None


def test_list_all_is_ordered_by_name() -> None:
    repository = DjangoTagRepository()
    for name in ("Zeta", "alpha", "Mid"):
        repository.get_or_create(name)

    assert [tag.name for tag in repository.list_all()] == ["Mid", "Zeta", "alpha"]


def test_tag_slug_follows_a_rename() -> None:
    repository = DjangoTagRepository()
    tag = repository.get_or_create("Fresh Produce")
    model = TagModel.objects.get(pk=_present(tag.id).value)

    model.name = "Fresh Bakery"
    model.save()
    model.refresh_from_db()

    assert model.slug == "fresh-bakery"


# ---------------------------------------------------------------------------
# Shopping lists
# ---------------------------------------------------------------------------


def test_shopping_list_round_trip_preserves_every_field() -> None:
    repository = DjangoShoppingListRepository()
    completed_at = NOW - timedelta(days=2)
    shopping_list = ShoppingList.create(
        user_id=_user_id(),
        name="  Weekly groceries ",
        now=NOW,
        priority=ListPriority.HIGH,
    )
    shopping_list.mark_as_completed(now=completed_at)

    saved = repository.save(shopping_list)
    loaded = _present(repository.get_by_id(ShoppingListId(_present(saved.id).value)))

    assert loaded.name == "Weekly groceries"
    assert loaded.priority is ListPriority.HIGH
    assert loaded.status is ItemStatus.PURCHASED
    assert loaded.is_active is True
    assert loaded.completed_at is not None
    # Postgres stores microseconds; compare within a second.
    assert abs((loaded.completed_at - completed_at).total_seconds()) < 1


def test_get_by_user_id_honours_the_active_only_flag() -> None:
    repository = DjangoShoppingListRepository()
    user: Any = UserFactory()
    active: Any = ShoppingListFactory(user=user, name="Active")
    deleted: Any = ShoppingListFactory(user=user, name="Deleted", is_active=False)

    only_active = repository.get_by_user_id(UserId(value=user.pk), active_only=True)
    everything = repository.get_by_user_id(UserId(value=user.pk), active_only=False)

    assert [_present(entry.id).value for entry in only_active] == [active.pk]
    assert {_present(entry.id).value for entry in everything} == {active.pk, deleted.pk}


def test_get_by_user_id_is_scoped_to_the_owner() -> None:
    repository = DjangoShoppingListRepository()
    owner: Any = UserFactory()
    ShoppingListFactory(user=owner)
    stranger: Any = UserFactory()

    assert repository.get_by_user_id(UserId(value=stranger.pk)) == []


def test_soft_delete_and_restore_persist_the_flag() -> None:
    repository = DjangoShoppingListRepository()
    shopping_list: Any = ShoppingListFactory()
    shopping_list_id = ShoppingListId(shopping_list.pk)

    repository.soft_delete(shopping_list_id)
    assert _present(repository.get_by_id(shopping_list_id)).is_active is False

    repository.restore(shopping_list_id)
    assert _present(repository.get_by_id(shopping_list_id)).is_active is True


def test_soft_delete_of_an_unknown_list_reports_not_found() -> None:
    repository = DjangoShoppingListRepository()

    with pytest.raises(ShoppingListNotFound):
        repository.soft_delete(ShoppingListId(uuid4()))


def test_update_of_an_unknown_list_reports_not_found() -> None:
    repository = DjangoShoppingListRepository()
    orphan = ShoppingList.create(user_id=_user_id(), name="Ghost", now=NOW)
    orphan.id = ShoppingListId(uuid4())

    with pytest.raises(ShoppingListNotFound):
        repository.update(orphan)


def test_update_persists_name_completion_and_the_active_flag() -> None:
    repository = DjangoShoppingListRepository()
    shopping_list = repository.save(
        ShoppingList.create(user_id=_user_id(), name="Groceries", now=NOW)
    )
    shopping_list.mark_as_completed(now=NOW)
    shopping_list.soft_delete()
    shopping_list.rename("Groceries and household")

    updated = repository.update(shopping_list)

    assert updated.name == "Groceries and household"
    assert updated.status is ItemStatus.PURCHASED
    assert updated.is_active is False
    stored = ShoppingListModel.objects.get(pk=_present(updated.id).value)
    assert stored.completed_at is not None
    assert stored.is_active is False


# ---------------------------------------------------------------------------
# Shopping list items
# ---------------------------------------------------------------------------


def _saved_list_item(**kwargs: Any) -> tuple[Any, ShoppingListItem]:
    repository = DjangoShoppingListItemRepository()
    parent: Any = ShoppingListFactory()
    item = ShoppingListItem.create(
        shopping_list_id=ShoppingListId(parent.pk),
        quantity=kwargs.pop("quantity", Quantity(1)),
        **kwargs,
    )
    return repository, repository.save(item)


def test_shopping_list_item_round_trip() -> None:
    repository, saved = _saved_list_item(
        name="  Whole milk ", quantity=Quantity(3), details="one liter"
    )

    loaded = _present(
        repository.get_by_id(ShoppingListItemId(_present(saved.id).value))
    )

    assert loaded.name == "Whole milk"
    assert int(loaded.quantity) == 3
    assert loaded.details == "one liter"
    assert loaded.status is ItemStatus.PENDING


def test_absent_details_round_trip_as_none() -> None:
    repository, saved = _saved_list_item(name="Bread")

    loaded = _present(
        repository.get_by_id(ShoppingListItemId(_present(saved.id).value))
    )

    assert loaded.details is None


def test_items_are_listed_by_parent_list() -> None:
    repository = DjangoShoppingListItemRepository()
    first: Any = ShoppingListFactory()
    second: Any = ShoppingListFactory()
    for parent, name in ((first, "Milk"), (second, "Rope")):
        repository.save(
            ShoppingListItem.create(
                shopping_list_id=ShoppingListId(parent.pk),
                name=name,
                quantity=Quantity(1),
            )
        )

    owned = repository.get_by_list_id(ShoppingListId(first.pk))

    assert [item.name for item in owned] == ["Milk"]


def test_item_tags_survive_a_round_trip() -> None:
    tags = DjangoTagRepository()
    repository, saved = _saved_list_item(
        name="Milk", tags=[tags.get_or_create("Dairy"), tags.get_or_create("Urgent")]
    )

    loaded = _present(
        repository.get_by_id(ShoppingListItemId(_present(saved.id).value))
    )

    assert {tag.name for tag in loaded.tags} == {"Dairy", "Urgent"}


def test_updating_tags_replaces_the_previous_set() -> None:
    tags = DjangoTagRepository()
    repository, saved = _saved_list_item(
        name="Milk", tags=[tags.get_or_create("Dairy")]
    )

    saved.tags = [tags.get_or_create("Bakery")]
    repository.update(saved)

    reloaded = _present(
        repository.get_by_id(ShoppingListItemId(_present(saved.id).value))
    )
    assert {tag.name for tag in reloaded.tags} == {"Bakery"}


def test_deleting_an_item_removes_it_but_keeps_the_catalogue() -> None:
    tags = DjangoTagRepository()
    repository, saved = _saved_list_item(
        name="Milk", tags=[tags.get_or_create("Dairy")]
    )
    item_id = ShoppingListItemId(_present(saved.id).value)
    tag_id = TagId(_present(saved.tags[0].id).value)

    repository.delete(item_id)

    assert repository.get_by_id(item_id) is None
    # The catalogue entry itself survives; only the association is gone.
    assert tags.get_by_id(tag_id) is not None


def test_deleting_an_unknown_item_reports_not_found() -> None:
    repository = DjangoShoppingListItemRepository()

    with pytest.raises(ShoppingListItemNotFound):
        repository.delete(ShoppingListItemId(uuid4()))


# ---------------------------------------------------------------------------
# Wishlist
# ---------------------------------------------------------------------------


def test_wishlist_round_trip() -> None:
    repository = DjangoWishlistRepository()
    wishlist = Wishlist.create(user_id=_user_id(), now=NOW)

    saved = repository.save(wishlist)
    loaded = _present(repository.get_by_id(WishlistId(_present(saved.id).value)))

    assert loaded.name == "My Wishlist"
    assert loaded.status is ItemStatus.PENDING
    assert repository.get_by_user_id(loaded.user_id) is not None


def test_a_user_cannot_hold_a_second_wishlist() -> None:
    repository = DjangoWishlistRepository()
    user_id = _user_id()
    repository.save(Wishlist.create(user_id=user_id, now=NOW))

    with pytest.raises(WishlistAlreadyExists):
        repository.save(Wishlist.create(user_id=user_id, now=NOW))


def test_get_by_user_id_returns_none_without_a_wishlist() -> None:
    repository = DjangoWishlistRepository()

    assert repository.get_by_user_id(_user_id()) is None


def test_wishlist_completion_persists() -> None:
    repository = DjangoWishlistRepository()
    wishlist = repository.save(Wishlist.create(user_id=_user_id(), now=NOW))

    wishlist.mark_as_completed(now=NOW)
    repository.update(wishlist)

    loaded = _present(repository.get_by_id(WishlistId(_present(wishlist.id).value)))
    assert loaded.status is ItemStatus.PURCHASED
    assert loaded.completed_at is not None


def test_deleting_a_user_cascades_to_their_wishlist() -> None:
    user: Any = UserFactory()
    wishlist: Any = WishlistFactory(user=user)
    item = DjangoWishlistItemRepository().save(
        WishlistItem.create(wishlist_id=WishlistId(wishlist.pk), name="Lamp")
    )
    wishlist_id = wishlist.pk
    item_id = _present(item.id).value

    user.delete()

    assert WishlistModel.objects.filter(pk=wishlist_id).exists() is False
    assert WishlistItemModel.objects.filter(pk=item_id).exists() is False


# ---------------------------------------------------------------------------
# Wishlist items
# ---------------------------------------------------------------------------


def _saved_wishlist_item(**kwargs: Any) -> tuple[Any, WishlistItem]:
    repository = DjangoWishlistItemRepository()
    parent: Any = WishlistFactory()
    item = WishlistItem.create(wishlist_id=WishlistId(parent.pk), **kwargs)
    return repository, repository.save(item)


def test_wishlist_item_round_trip_preserves_links_and_price() -> None:
    repository, saved = _saved_wishlist_item(
        name="  Espresso machine ",
        link=Link("https://example.com/machine"),
        image_link=Link("https://example.com/machine.png"),
        description="For the kitchen",
        estimated_price=EstimatedPrice(Decimal("399.90")),
        priority=WishlistPriority.MUST_HAVE,
    )

    loaded = _present(repository.get_by_id(WishlistItemId(_present(saved.id).value)))

    assert loaded.name == "Espresso machine"
    assert str(loaded.link) == "https://example.com/machine"
    assert str(loaded.image_link) == "https://example.com/machine.png"
    assert loaded.description == "For the kitchen"
    assert _present(loaded.estimated_price).amount == Decimal("399.90")
    assert loaded.priority is WishlistPriority.MUST_HAVE


def test_absent_wishlist_item_fields_round_trip_as_none() -> None:
    repository, saved = _saved_wishlist_item(name="Lamp")

    loaded = _present(repository.get_by_id(WishlistItemId(_present(saved.id).value)))

    assert loaded.link is None
    assert loaded.image_link is None
    assert loaded.description is None
    assert loaded.estimated_price is None


def test_wishlist_items_are_listed_by_parent() -> None:
    repository = DjangoWishlistItemRepository()
    first: Any = WishlistFactory()
    second: Any = WishlistFactory()
    for parent, name in ((first, "Lamp"), (second, "Rug")):
        repository.save(
            WishlistItem.create(wishlist_id=WishlistId(parent.pk), name=name)
        )

    owned = repository.get_by_wishlist_id(WishlistId(first.pk))

    assert [item.name for item in owned] == ["Lamp"]


def test_wishlist_item_tags_survive_a_round_trip() -> None:
    tags = DjangoTagRepository()
    repository, saved = _saved_wishlist_item(
        name="Lamp", tags=[tags.get_or_create("Home")]
    )

    loaded = _present(repository.get_by_id(WishlistItemId(_present(saved.id).value)))

    assert {tag.name for tag in loaded.tags} == {"Home"}


def test_marking_a_wishlist_item_purchased_persists_the_status() -> None:
    repository, saved = _saved_wishlist_item(name="Lamp")

    saved.mark_as_purchased()
    repository.update(saved)

    loaded = _present(repository.get_by_id(WishlistItemId(_present(saved.id).value)))
    assert loaded.status is ItemStatus.PURCHASED
