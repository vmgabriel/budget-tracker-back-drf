"""Wishlist and tag use-case tests."""

import uuid
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.purchases.application.commands import (
    AddItemToWishlistCommand,
    AddTagsToWishlistItemCommand,
    CreateTagCommand,
    DeleteWishlistItemCommand,
    GetOrCreateWishlistCommand,
    ListTagsCommand,
    MarkWishlistItemAsPurchasedCommand,
    RemoveTagsFromWishlistItemCommand,
    UpdateWishlistCommand,
    UpdateWishlistItemCommand,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.use_cases.tags import CreateTag, ListTags
from apps.purchases.application.use_cases.wishlists import (
    AddItemToWishlist,
    AddTagsToWishlistItem,
    DeleteWishlistItem,
    GetOrCreateWishlist,
    GetWishlist,
    MarkWishlistItemAsPurchased,
    RemoveTagsFromWishlistItem,
    UpdateWishlist,
    UpdateWishlistItem,
)
from apps.purchases.domain.entities import Wishlist
from apps.purchases.domain.exceptions import (
    TagNotFound,
    WishlistAlreadyExists,
    WishlistItemNotFound,
    WishlistNotFound,
)
from apps.purchases.domain.value_objects import (
    ItemStatus,
    UserId,
    WishlistPriority,
)
from tests.unit.purchases.fakes import (
    FakeClock,
    FakeTagRepository,
    FakeWishlistItemRepository,
    FakeWishlistRepository,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def owner_id() -> str:
    return str(uuid4())


@pytest.fixture
def stranger_id() -> str:
    return str(uuid4())


@pytest.fixture
def wishlists() -> FakeWishlistRepository:
    return FakeWishlistRepository()


@pytest.fixture
def items() -> FakeWishlistItemRepository:
    return FakeWishlistItemRepository()


@pytest.fixture
def tags() -> FakeTagRepository:
    return FakeTagRepository()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def _make_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> str:
    details = GetOrCreateWishlist(wishlists, items, clock).execute(
        GetOrCreateWishlistCommand(user_id=uuid.UUID(owner_id))
    )
    return str(details.id.value)


def _make_item(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    owner_id: str,
    wishlist_id: str,
    name: str = "Espresso machine",
    **kwargs: object,
) -> str:
    details = AddItemToWishlist(wishlists, items).execute(
        AddItemToWishlistCommand(
            wishlist_id=uuid.UUID(wishlist_id),
            user_id=uuid.UUID(owner_id),
            name=name,
            **kwargs,  # type: ignore[arg-type]
        )
    )
    return str(details.items[-1].id.value)


# ---------------------------------------------------------------------------
# Get / create
# ---------------------------------------------------------------------------


def test_first_access_creates_the_single_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    details = GetOrCreateWishlist(wishlists, items, clock).execute(
        GetOrCreateWishlistCommand(user_id=uuid.UUID(owner_id))
    )

    assert details.name == "My Wishlist"
    assert details.status is ItemStatus.PENDING
    assert details.is_active is True


def test_second_access_returns_the_same_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    use_case = GetOrCreateWishlist(wishlists, items, clock)
    command = GetOrCreateWishlistCommand(user_id=uuid.UUID(owner_id))

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert first.id == second.id
    assert len(wishlists.wishlists) == 1


def test_a_second_wishlist_for_the_same_user_is_rejected(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    _make_wishlist(wishlists, items, clock, owner_id)
    duplicate = Wishlist.create(
        user_id=UserId(value=uuid.UUID(owner_id)), now=clock.now()
    )

    with pytest.raises(WishlistAlreadyExists):
        wishlists.save(duplicate)


def test_get_wishlist_does_not_create_one(
    wishlists: FakeWishlistRepository, items: FakeWishlistItemRepository
) -> None:
    with pytest.raises(WishlistNotFound):
        GetWishlist(wishlists, items).execute(
            GetOrCreateWishlistCommand(user_id=uuid4())
        )


def test_get_wishlist_returns_the_owned_list(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    details = GetWishlist(wishlists, items).execute(
        GetOrCreateWishlistCommand(user_id=uuid.UUID(owner_id))
    )

    assert str(details.id.value) == wishlist_id


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_update_renames_the_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    details = UpdateWishlist(wishlists).execute(
        UpdateWishlistCommand(
            wishlist_id=uuid.UUID(wishlist_id),
            user_id=uuid.UUID(owner_id),
            name="  Holiday  gifts ",
        )
    )

    assert details.name == "Holiday gifts"


def test_update_requires_a_field(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    with pytest.raises(InvalidPurchasesInput, match="At least one"):
        UpdateWishlist(wishlists).execute(
            UpdateWishlistCommand(
                wishlist_id=uuid.UUID(wishlist_id), user_id=uuid.UUID(owner_id)
            )
        )


def test_update_rejects_a_foreign_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    with pytest.raises(WishlistNotFound):
        UpdateWishlist(wishlists).execute(
            UpdateWishlistCommand(
                wishlist_id=uuid.UUID(wishlist_id),
                user_id=uuid.UUID(stranger_id),
                name="Mine",
            )
        )


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def test_add_item_keeps_link_price_and_priority(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    details = AddItemToWishlist(wishlists, items).execute(
        AddItemToWishlistCommand(
            wishlist_id=uuid.UUID(wishlist_id),
            user_id=uuid.UUID(owner_id),
            name="Espresso machine",
            link="https://example.com/machine",
            description="  For the kitchen  ",
            estimated_price=Decimal("399.90"),
            priority="must_have",
        )
    )

    item = details.items[-1]
    assert item.link == "https://example.com/machine"
    assert item.image_link is None
    assert item.description == "For the kitchen"
    assert item.estimated_price == Decimal("399.90")
    assert item.priority is WishlistPriority.MUST_HAVE


def test_add_item_rejects_a_malformed_link(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    with pytest.raises(InvalidPurchasesInput, match="Link"):
        AddItemToWishlist(wishlists, items).execute(
            AddItemToWishlistCommand(
                wishlist_id=uuid.UUID(wishlist_id),
                user_id=uuid.UUID(owner_id),
                name="Item",
                link="not-a-url",
            )
        )


def test_add_item_rejects_a_negative_price(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)

    with pytest.raises(InvalidPurchasesInput, match="cannot be negative"):
        AddItemToWishlist(wishlists, items).execute(
            AddItemToWishlistCommand(
                wishlist_id=uuid.UUID(wishlist_id),
                user_id=uuid.UUID(owner_id),
                name="Item",
                estimated_price=Decimal("-1.00"),
            )
        )


def test_update_item_applies_a_partial_change(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)

    details = UpdateWishlistItem(wishlists, items).execute(
        UpdateWishlistItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            priority="nice_to_have",
        )
    )

    assert details.priority is WishlistPriority.NICE_TO_HAVE
    assert details.name == "Espresso machine"


def test_update_item_requires_a_field(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)

    with pytest.raises(InvalidPurchasesInput, match="At least one"):
        UpdateWishlistItem(wishlists, items).execute(
            UpdateWishlistItemCommand(
                item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
            )
        )


def test_delete_item_reopens_a_completed_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)
    MarkWishlistItemAsPurchased(wishlists, items, clock).execute(
        MarkWishlistItemAsPurchasedCommand(
            item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
        )
    )

    details = DeleteWishlistItem(wishlists, items, clock).execute(
        DeleteWishlistItemCommand(
            item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
        )
    )

    assert details.items == []
    assert details.status is ItemStatus.PENDING
    assert details.completed_at is None


def test_marking_purchased_completes_the_wishlist(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    first = _make_item(wishlists, items, owner_id, wishlist_id, name="Lamp")
    second = _make_item(wishlists, items, owner_id, wishlist_id, name="Rug")

    partial = MarkWishlistItemAsPurchased(wishlists, items, clock).execute(
        MarkWishlistItemAsPurchasedCommand(
            item_id=uuid.UUID(first), user_id=uuid.UUID(owner_id)
        )
    )
    assert partial.status is ItemStatus.PENDING

    completed = MarkWishlistItemAsPurchased(wishlists, items, clock).execute(
        MarkWishlistItemAsPurchasedCommand(
            item_id=uuid.UUID(second), user_id=uuid.UUID(owner_id)
        )
    )
    assert completed.status is ItemStatus.PURCHASED
    assert completed.completed_at == clock.now()


def test_marking_purchased_rejects_a_foreign_item(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)

    with pytest.raises(WishlistItemNotFound):
        MarkWishlistItemAsPurchased(wishlists, items, clock).execute(
            MarkWishlistItemAsPurchasedCommand(
                item_id=uuid.UUID(item_id), user_id=uuid.UUID(stranger_id)
            )
        )


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_wishlist_item_tags_are_added_and_removed(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)

    added = AddTagsToWishlistItem(wishlists, items, tags).execute(
        AddTagsToWishlistItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            tag_names=["Home", "Gift"],
        )
    )
    assert {tag.name for tag in added.tags} == {"Home", "Gift"}

    removed = RemoveTagsFromWishlistItem(wishlists, items, tags).execute(
        RemoveTagsFromWishlistItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            tag_ids=[added.tags[0].id.value],
        )
    )
    assert [tag.name for tag in removed.tags] == [added.tags[1].name]


def test_removing_an_unknown_wishlist_tag_reports_not_found(
    wishlists: FakeWishlistRepository,
    items: FakeWishlistItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    wishlist_id = _make_wishlist(wishlists, items, clock, owner_id)
    item_id = _make_item(wishlists, items, owner_id, wishlist_id)

    with pytest.raises(TagNotFound):
        RemoveTagsFromWishlistItem(wishlists, items, tags).execute(
            RemoveTagsFromWishlistItemCommand(
                item_id=uuid.UUID(item_id),
                user_id=uuid.UUID(owner_id),
                tag_ids=[uuid4()],
            )
        )


# ---------------------------------------------------------------------------
# Tag catalogue
# ---------------------------------------------------------------------------


def test_create_tag_is_idempotent(tags: FakeTagRepository) -> None:
    use_case = CreateTag(tags)

    first = use_case.execute(CreateTagCommand(name="Dairy"))
    second = use_case.execute(CreateTagCommand(name="  dairy "))

    assert first == second
    assert len(tags.list_all()) == 1


def test_create_tag_derives_the_slug(tags: FakeTagRepository) -> None:
    details = CreateTag(tags).execute(CreateTagCommand(name="Fresh Produce"))

    assert (details.name, details.slug) == ("Fresh Produce", "fresh-produce")


def test_create_tag_rejects_a_blank_name(tags: FakeTagRepository) -> None:
    with pytest.raises(InvalidPurchasesInput, match="cannot be empty"):
        CreateTag(tags).execute(CreateTagCommand(name="   "))


def test_list_tags_returns_the_catalogue_by_name(tags: FakeTagRepository) -> None:
    for name in ("Zeta", "alpha", "Mid"):
        CreateTag(tags).execute(CreateTagCommand(name=name))

    assert [tag.name for tag in ListTags(tags).execute(ListTagsCommand())] == [
        "Mid",
        "Zeta",
        "alpha",
    ]
