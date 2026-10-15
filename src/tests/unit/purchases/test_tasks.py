"""Unit tests for the purchases archival sweep."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.purchases.domain.value_objects import ArchiveDelay
from apps.purchases.infrastructure.persistence.preferences import (
    ConfiguredArchiveDelayReader,
)
from apps.purchases.infrastructure.tasks import ArchivalSweep
from tests.unit.purchases.fakes import (
    FakeClock,
    FakeShoppingListItemRepository,
    FakeShoppingListRepository,
    FakeWishlistItemRepository,
    FakeWishlistRepository,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 3, 10, 3, 0, tzinfo=UTC)


class StubDelays:
    """Answer with one delay for everyone, so the sweep logic can be isolated."""

    def __init__(self, days: Decimal = Decimal("7.0")) -> None:
        self._delay = ArchiveDelay(days)

    def get_archive_delay(self, user_id: object) -> ArchiveDelay:
        return self._delay


def _completed_lists(
    clock: FakeClock, *ages_days: int
) -> tuple[FakeShoppingListRepository, FakeShoppingListItemRepository]:
    """Return repositories holding one purchased list per given age.

    A completed list needs real, purchased items: the domain decides
    completion by inspecting them, so a bare ``mark_as_completed`` would be
    inconsistent state rather than a fair test fixture.
    """
    from apps.purchases.domain.entities import ShoppingList, ShoppingListItem
    from apps.purchases.domain.value_objects import ItemStatus, Quantity, UserId

    lists = FakeShoppingListRepository()
    items = FakeShoppingListItemRepository()
    for days in ages_days:
        shopping_list = ShoppingList.create(
            user_id=UserId(value=uuid4()), name=f"List {days}", now=clock.now()
        )
        lists.save(shopping_list)
        list_id = shopping_list.id
        assert list_id is not None
        item = items.save(
            ShoppingListItem.create(
                shopping_list_id=list_id,
                name=f"Item {days}",
                quantity=Quantity(1),
                status=ItemStatus.PURCHASED,
            )
        )
        shopping_list.add_item(item)
        shopping_list.mark_as_completed(now=clock.now() - timedelta(days=days))
    return lists, items


def _sweep(
    lists: FakeShoppingListRepository,
    items: FakeShoppingListItemRepository,
    wishlists: FakeWishlistRepository | None = None,
    delays: StubDelays | None = None,
    clock: FakeClock | None = None,
) -> ArchivalSweep:
    return ArchivalSweep(
        shopping_lists=lists,
        shopping_list_items=items,
        wishlists=wishlists or FakeWishlistRepository(),
        wishlist_items=FakeWishlistItemRepository(),
        delays=delays or StubDelays(),
        clock=clock or FakeClock(NOW),
    )


def test_a_list_past_the_delay_is_archived() -> None:
    lists, items = _completed_lists(FakeClock(NOW), 8)
    stale_id = next(iter(lists.shopping_lists))

    result = _sweep(lists, items).run()

    assert result["archived"] == 1
    assert lists.shopping_lists[stale_id].is_active is False


def test_a_list_within_the_delay_is_left_alone() -> None:
    lists, items = _completed_lists(FakeClock(NOW), 5)
    fresh_id = next(iter(lists.shopping_lists))

    result = _sweep(lists, items).run()

    assert result["archived"] == 0
    assert lists.shopping_lists[fresh_id].is_active is True


def test_the_delay_boundary_is_exclusive() -> None:
    """Exactly seven days is not yet stale; the domain says "greater than"."""
    lists, items = _completed_lists(FakeClock(NOW), 7)

    assert _sweep(lists, items).run()["archived"] == 0


def test_a_shorter_user_delay_is_honoured() -> None:
    lists, items = _completed_lists(FakeClock(NOW), 3)

    assert (
        _sweep(lists, items, delays=StubDelays(Decimal("2.5"))).run()["archived"] == 1
    )


def test_the_sweep_reports_what_it_examined() -> None:
    lists, items = _completed_lists(FakeClock(NOW), 8, 5)

    result = _sweep(lists, items).run()

    assert result["shopping_lists_examined"] == 2
    assert result["archived"] == 1


def test_running_twice_archives_nothing_extra() -> None:
    lists, items = _completed_lists(FakeClock(NOW), 8)
    sweep = _sweep(lists, items)

    first = sweep.run()
    second = sweep.run()

    assert first["archived"] == 1
    assert second["archived"] == 0


def test_a_pending_list_is_never_archived() -> None:
    """A list that was never completed must survive an arbitrarily old sweep."""
    from apps.purchases.domain.entities import ShoppingList
    from apps.purchases.domain.value_objects import UserId

    lists = FakeShoppingListRepository()
    pending = ShoppingList.create(user_id=UserId(value=uuid4()), name="Open", now=NOW)
    lists.save(pending)

    assert _sweep(lists, FakeShoppingListItemRepository()).run()["archived"] == 0


def test_a_completed_list_with_no_items_is_not_archived() -> None:
    """The regression this hydration exists to prevent.

    A stale completion stamp on a list whose items never get loaded would read
    as "nothing was bought" and archive nothing. The guard is that items are
    re-read before the decision, which this test pins down: an item that is
    still pending must block archival even though the list is stamped
    completed and long past due.
    """
    from apps.purchases.domain.entities import ShoppingList, ShoppingListItem
    from apps.purchases.domain.value_objects import (
        ItemStatus,
        Quantity,
        UserId,
    )

    lists = FakeShoppingListRepository()
    items = FakeShoppingListItemRepository()
    shopping_list = ShoppingList.create(
        user_id=UserId(value=uuid4()), name="Mixed", now=NOW
    )
    lists.save(shopping_list)
    list_id = shopping_list.id
    assert list_id is not None
    pending_item = items.save(
        ShoppingListItem.create(
            shopping_list_id=list_id,
            name="Still to buy",
            quantity=Quantity(1),
            status=ItemStatus.PENDING,
        )
    )
    shopping_list.add_item(pending_item)
    shopping_list.mark_as_completed(now=NOW - timedelta(days=30))

    assert _sweep(lists, items).run()["archived"] == 0


# ---------------------------------------------------------------------------
# Archive delay reader
# ---------------------------------------------------------------------------


def test_the_reader_serves_the_configured_default() -> None:
    reader = ConfiguredArchiveDelayReader()

    assert reader.get_archive_delay(uuid4()).days == Decimal("7.0")


def test_the_reader_can_be_seeded_with_another_delay() -> None:
    reader = ConfiguredArchiveDelayReader(default_days=Decimal("3"))

    assert reader.get_archive_delay(uuid4()).days == Decimal("3")


def test_a_corrupt_delay_falls_back_instead_of_raising() -> None:
    """A periodic job must not wedge because one stored value is unusable."""
    reader = ConfiguredArchiveDelayReader(default_days=-5)  # type: ignore[arg-type]

    assert reader.get_archive_delay(uuid4()).days == Decimal("7.0")
