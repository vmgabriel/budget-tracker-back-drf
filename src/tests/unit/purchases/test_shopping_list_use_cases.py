"""Shopping list use-case tests."""

import uuid
from uuid import uuid4

import pytest

from apps.purchases.application.commands import (
    AddItemToShoppingListCommand,
    AddTagsToItemCommand,
    CreateShoppingListCommand,
    DeleteShoppingListItemCommand,
    GetShoppingListCommand,
    ListShoppingListsCommand,
    MarkItemAsPurchasedCommand,
    RemoveTagsFromItemCommand,
    RestoreShoppingListCommand,
    SoftDeleteShoppingListCommand,
    UpdateShoppingListCommand,
    UpdateShoppingListItemCommand,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.application.use_cases.shopping_lists import (
    AddItemToShoppingList,
    AddTagsToItem,
    CreateShoppingList,
    DeleteShoppingListItem,
    GetShoppingList,
    ListInactiveShoppingLists,
    ListUserShoppingLists,
    MarkItemAsPurchased,
    RemoveTagsFromItem,
    RestoreShoppingList,
    SoftDeleteShoppingList,
    UpdateShoppingList,
    UpdateShoppingListItem,
)
from apps.purchases.domain.exceptions import (
    ShoppingListItemNotFound,
    ShoppingListNotFound,
    TagNotFound,
)
from apps.purchases.domain.value_objects import ItemStatus, ListPriority
from tests.unit.purchases.fakes import (
    FakeClock,
    FakeShoppingListItemRepository,
    FakeShoppingListRepository,
    FakeTagRepository,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def owner_id() -> str:
    return str(uuid4())


@pytest.fixture
def stranger_id() -> str:
    return str(uuid4())


@pytest.fixture
def lists() -> FakeShoppingListRepository:
    return FakeShoppingListRepository()


@pytest.fixture
def items() -> FakeShoppingListItemRepository:
    return FakeShoppingListItemRepository()


@pytest.fixture
def tags() -> FakeTagRepository:
    return FakeTagRepository()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def _make_list(
    lists: FakeShoppingListRepository,
    clock: FakeClock,
    owner_id: str,
    name: str = "Groceries",
    priority: str = "medium",
) -> str:
    details = CreateShoppingList(lists, clock).execute(
        CreateShoppingListCommand(
            user_id=uuid.UUID(owner_id), name=name, priority=priority
        )
    )
    return str(details.id.value)


def _make_item(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
    list_id: str,
    name: str = "Milk",
    quantity: int = 2,
) -> str:
    details = AddItemToShoppingList(lists, items).execute(
        AddItemToShoppingListCommand(
            list_id=uuid.UUID(list_id),
            user_id=uuid.UUID(owner_id),
            name=name,
            quantity=quantity,
        )
    )
    return str(details.items[-1].id.value)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_create_persists_a_pending_active_list(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    details = CreateShoppingList(lists, clock).execute(
        CreateShoppingListCommand(
            user_id=uuid.UUID(owner_id), name="  Weekly  groceries ", priority="HIGH"
        )
    )

    assert details.name == "Weekly groceries"
    assert details.priority is ListPriority.HIGH
    assert details.status is ItemStatus.PENDING
    assert details.is_active is True
    assert details.completed_at is None
    assert details.items == []


def test_create_rejects_an_unknown_priority(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    with pytest.raises(InvalidPurchasesInput, match="must be one of"):
        CreateShoppingList(lists, clock).execute(
            CreateShoppingListCommand(
                user_id=uuid.UUID(owner_id), name="Groceries", priority="urgent"
            )
        )


def test_create_rejects_a_blank_name(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    with pytest.raises(InvalidPurchasesInput, match="cannot be empty"):
        CreateShoppingList(lists, clock).execute(
            CreateShoppingListCommand(user_id=uuid.UUID(owner_id), name="   ")
        )


# ---------------------------------------------------------------------------
# Get / list
# ---------------------------------------------------------------------------


def test_get_returns_the_list_with_its_items(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    _make_item(lists, items, clock, owner_id, list_id, name="Milk")

    details = GetShoppingList(lists, items).execute(
        GetShoppingListCommand(list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id))
    )

    assert [item.name for item in details.items] == ["Milk"]
    assert details.items[0].quantity == 2


def test_get_hides_a_list_owned_by_somebody_else(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    with pytest.raises(ShoppingListNotFound):
        GetShoppingList(lists, items).execute(
            GetShoppingListCommand(
                list_id=uuid.UUID(list_id), user_id=uuid.UUID(stranger_id)
            )
        )


def test_get_hides_an_unknown_list(
    lists: FakeShoppingListRepository, items: FakeShoppingListItemRepository
) -> None:
    with pytest.raises(ShoppingListNotFound):
        GetShoppingList(lists, items).execute(
            GetShoppingListCommand(list_id=uuid4(), user_id=uuid4())
        )


def test_active_listing_excludes_soft_deleted_lists(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    kept = _make_list(lists, clock, owner_id, name="Kept")
    removed = _make_list(lists, clock, owner_id, name="Removed")
    SoftDeleteShoppingList(lists).execute(
        SoftDeleteShoppingListCommand(
            list_id=uuid.UUID(removed), user_id=uuid.UUID(owner_id)
        )
    )

    command = ListShoppingListsCommand(user_id=uuid.UUID(owner_id))
    active = ListUserShoppingLists(lists).execute(command)
    inactive = ListInactiveShoppingLists(lists).execute(command)

    assert [entry.id.value for entry in active] == [uuid.UUID(kept)]
    assert [entry.id.value for entry in inactive] == [uuid.UUID(removed)]
    assert all(entry.is_active is False for entry in inactive)


def test_active_listing_is_scoped_to_the_owner(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    _make_list(lists, clock, owner_id)
    _make_list(lists, clock, str(uuid4()))

    assert (
        len(
            ListUserShoppingLists(lists).execute(
                ListShoppingListsCommand(user_id=uuid.UUID(owner_id))
            )
        )
        == 1
    )


# ---------------------------------------------------------------------------
# Update / soft delete / restore
# ---------------------------------------------------------------------------


def test_update_applies_a_partial_change(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    details = UpdateShoppingList(lists).execute(
        UpdateShoppingListCommand(
            list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id), priority="high"
        )
    )

    assert details.priority is ListPriority.HIGH
    assert details.name == "Groceries"


def test_update_requires_at_least_one_field(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    with pytest.raises(InvalidPurchasesInput, match="At least one"):
        UpdateShoppingList(lists).execute(
            UpdateShoppingListCommand(
                list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id)
            )
        )


def test_soft_delete_hides_and_restore_brings_back(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    deleted = SoftDeleteShoppingList(lists).execute(
        SoftDeleteShoppingListCommand(
            list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id)
        )
    )
    assert deleted.is_active is False

    restored = RestoreShoppingList(lists).execute(
        RestoreShoppingListCommand(
            list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id)
        )
    )
    assert restored.is_active is True
    assert [entry.value for entry in lists.restored] == [uuid.UUID(list_id)]
    assert [entry.value for entry in lists.soft_deleted] == [uuid.UUID(list_id)]


def test_restore_rejects_a_foreign_list(
    lists: FakeShoppingListRepository, clock: FakeClock, owner_id: str, stranger_id: str
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    with pytest.raises(ShoppingListNotFound):
        RestoreShoppingList(lists).execute(
            RestoreShoppingListCommand(
                list_id=uuid.UUID(list_id), user_id=uuid.UUID(stranger_id)
            )
        )


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def test_add_item_defaults_to_quantity_one(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    details = AddItemToShoppingList(lists, items).execute(
        AddItemToShoppingListCommand(
            list_id=uuid.UUID(list_id), user_id=uuid.UUID(owner_id), name="Bread"
        )
    )

    assert [(item.name, item.quantity) for item in details.items] == [("Bread", 1)]
    assert details.items[0].status is ItemStatus.PENDING


def test_add_item_rejects_a_non_positive_quantity(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    with pytest.raises(InvalidPurchasesInput):
        AddItemToShoppingList(lists, items).execute(
            AddItemToShoppingListCommand(
                list_id=uuid.UUID(list_id),
                user_id=uuid.UUID(owner_id),
                name="Bread",
                quantity=0,
            )
        )


def test_add_item_rejects_a_foreign_list(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)

    with pytest.raises(ShoppingListNotFound):
        AddItemToShoppingList(lists, items).execute(
            AddItemToShoppingListCommand(
                list_id=uuid.UUID(list_id),
                user_id=uuid.UUID(stranger_id),
                name="Bread",
            )
        )


def test_update_item_applies_a_partial_change(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    details = UpdateShoppingListItem(lists, items).execute(
        UpdateShoppingListItemCommand(
            item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id), quantity=6
        )
    )

    assert details.quantity == 6
    assert details.name == "Milk"


def test_update_item_requires_at_least_one_field(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    with pytest.raises(InvalidPurchasesInput, match="At least one"):
        UpdateShoppingListItem(lists, items).execute(
            UpdateShoppingListItemCommand(
                item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
            )
        )


def test_delete_item_reopens_a_completed_list(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)
    command = MarkItemAsPurchasedCommand(
        item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
    )
    completed = MarkItemAsPurchased(lists, items, clock).execute(command)

    assert completed.status is ItemStatus.PURCHASED
    assert completed.completed_at == clock.now()

    details = DeleteShoppingListItem(lists, items, clock).execute(
        DeleteShoppingListItemCommand(
            item_id=uuid.UUID(item_id), user_id=uuid.UUID(owner_id)
        )
    )

    assert details.items == []
    assert details.status is ItemStatus.PENDING
    assert details.completed_at is None


# ---------------------------------------------------------------------------
# Purchased / completion coherence
# ---------------------------------------------------------------------------


def test_marking_the_last_item_purchased_completes_the_list(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    first = _make_item(lists, items, clock, owner_id, list_id, name="Milk")
    second = _make_item(lists, items, clock, owner_id, list_id, name="Bread")

    partial = MarkItemAsPurchased(lists, items, clock).execute(
        MarkItemAsPurchasedCommand(
            item_id=uuid.UUID(first), user_id=uuid.UUID(owner_id)
        )
    )
    assert partial.status is ItemStatus.PENDING
    assert partial.completed_at is None

    completed = MarkItemAsPurchased(lists, items, clock).execute(
        MarkItemAsPurchasedCommand(
            item_id=uuid.UUID(second), user_id=uuid.UUID(owner_id)
        )
    )
    assert completed.status is ItemStatus.PURCHASED
    assert completed.completed_at == clock.now()


def test_marking_purchased_rejects_a_foreign_item(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    with pytest.raises(ShoppingListItemNotFound):
        MarkItemAsPurchased(lists, items, clock).execute(
            MarkItemAsPurchasedCommand(
                item_id=uuid.UUID(item_id), user_id=uuid.UUID(stranger_id)
            )
        )


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


def test_adding_tags_creates_the_catalogue_entries(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    details = AddTagsToItem(lists, items, tags).execute(
        AddTagsToItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            tag_names=["Dairy", " urgent "],
        )
    )

    assert {tag.name for tag in details.tags} == {"Dairy", "urgent"}
    assert len(tags.list_all()) == 2


def test_adding_the_same_tag_twice_is_idempotent(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)
    command = AddTagsToItemCommand(
        item_id=uuid.UUID(item_id),
        user_id=uuid.UUID(owner_id),
        tag_names=["Dairy", "dairy"],
    )
    use_case = AddTagsToItem(lists, items, tags)

    first = use_case.execute(command)
    second = use_case.execute(command)

    assert len(second.tags) == len(first.tags) == 1
    assert len(tags.list_all()) == 1


def test_adding_tags_requires_at_least_one_name(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    with pytest.raises(InvalidPurchasesInput, match="tag name"):
        AddTagsToItem(lists, items, tags).execute(
            AddTagsToItemCommand(
                item_id=uuid.UUID(item_id),
                user_id=uuid.UUID(owner_id),
                tag_names=["  "],
            )
        )


def test_removing_tags_detaches_them_by_identity(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)
    add = AddTagsToItem(lists, items, tags)
    added = add.execute(
        AddTagsToItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            tag_names=["Dairy", "Bakery"],
        )
    )

    removed = RemoveTagsFromItem(lists, items, tags).execute(
        RemoveTagsFromItemCommand(
            item_id=uuid.UUID(item_id),
            user_id=uuid.UUID(owner_id),
            tag_ids=[added.tags[0].id.value],
        )
    )

    assert [tag.name for tag in removed.tags] == [added.tags[1].name]


def test_removing_an_unknown_tag_reports_not_found(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    with pytest.raises(TagNotFound):
        RemoveTagsFromItem(lists, items, tags).execute(
            RemoveTagsFromItemCommand(
                item_id=uuid.UUID(item_id),
                user_id=uuid.UUID(owner_id),
                tag_ids=[uuid4()],
            )
        )


def test_tagging_rejects_a_foreign_item(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    tags: FakeTagRepository,
    clock: FakeClock,
    owner_id: str,
    stranger_id: str,
) -> None:
    list_id = _make_list(lists, clock, owner_id)
    item_id = _make_item(lists, items, clock, owner_id, list_id)

    with pytest.raises(ShoppingListItemNotFound):
        AddTagsToItem(lists, items, tags).execute(
            AddTagsToItemCommand(
                item_id=uuid.UUID(item_id),
                user_id=uuid.UUID(stranger_id),
                tag_names=["Dairy"],
            )
        )
