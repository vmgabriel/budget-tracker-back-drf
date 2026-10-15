"""Celery task tests for the purchases archival sweep."""

from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.utils import timezone

from apps.purchases.infrastructure.persistence.models import (
    ShoppingListItemModel,
    ShoppingListModel,
    WishlistModel,
)
from apps.purchases.infrastructure.tasks import archive_completed_lists_celery
from tests.factories import (
    ShoppingListFactory,
    ShoppingListItemFactory,
    UserFactory,
    WishlistFactory,
    WishlistItemFactory,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _completed_list(user: Any, days_ago: int) -> Any:
    """Create an active list completed ``days_ago`` days back, all items bought."""
    shopping_list: Any = ShoppingListFactory(user=user, is_active=True)
    ShoppingListItemFactory(
        shopping_list=shopping_list, status="purchased", name="Milk"
    )
    ShoppingListModel.objects.filter(pk=shopping_list.pk).update(
        status="purchased",
        completed_at=timezone.now() - timedelta(days=days_ago),
    )
    shopping_list.refresh_from_db()
    return shopping_list


def _completed_wishlist(user: Any, days_ago: int) -> Any:
    wishlist: Any = WishlistFactory(user=user, is_active=True)
    WishlistItemFactory(wishlist=wishlist, status="purchased", name="Lamp")
    WishlistModel.objects.filter(pk=wishlist.pk).update(
        status="purchased",
        completed_at=timezone.now() - timedelta(days=days_ago),
    )
    wishlist.refresh_from_db()
    return wishlist


# ---------------------------------------------------------------------------
# The scenario from the task description
# ---------------------------------------------------------------------------


def test_archives_only_the_lists_past_the_delay() -> None:
    user = UserFactory()
    stale = _completed_list(user, days_ago=8)
    recent = _completed_list(user, days_ago=5)

    result = archive_completed_lists_celery.apply().get()

    stale.refresh_from_db()
    recent.refresh_from_db()
    assert stale.is_active is False
    assert recent.is_active is True
    assert result["archived"] == 1


def test_archiving_keeps_the_items_for_a_restore() -> None:
    user = UserFactory()
    stale = _completed_list(user, days_ago=8)

    archive_completed_lists_celery.apply().get()

    stale.refresh_from_db()
    assert stale.is_active is False
    # A soft delete, not a discard: the items survive so the owner can restore.
    assert ShoppingListItemModel.objects.filter(shopping_list=stale).count() == 1
    assert ShoppingListModel.objects.filter(pk=stale.pk).exists() is True


def test_a_list_within_the_delay_is_not_archived() -> None:
    """Six days is comfortably inside the seven-day default.

    The exact boundary is asserted in the unit tests with a frozen clock; here
    real time advances between creating the row and running the sweep, so an
    exactly-seven-day-old fixture would be microseconds past the boundary.
    """
    user = UserFactory()
    recent = _completed_list(user, days_ago=6)

    archive_completed_lists_celery.apply().get()

    recent.refresh_from_db()
    assert recent.is_active is True


def test_a_never_completed_list_is_left_alone() -> None:
    pending: Any = ShoppingListFactory(user=UserFactory(), is_active=True)

    archive_completed_lists_celery.apply().get()

    pending.refresh_from_db()
    assert pending.is_active is True


def test_a_list_with_an_unbought_item_is_not_archived() -> None:
    """A stale completion stamp must not outweigh a pending item."""
    user = UserFactory()
    shopping_list: Any = ShoppingListFactory(user=user, is_active=True)
    ShoppingListItemFactory(shopping_list=shopping_list, status="purchased")
    ShoppingListItemFactory(shopping_list=shopping_list, status="pending")
    ShoppingListModel.objects.filter(pk=shopping_list.pk).update(
        status="purchased", completed_at=timezone.now() - timedelta(days=30)
    )

    archive_completed_lists_celery.apply().get()

    shopping_list.refresh_from_db()
    assert shopping_list.is_active is True


def test_an_already_archived_list_is_not_touched_again() -> None:
    user = UserFactory()
    stale = _completed_list(user, days_ago=8)
    archive_completed_lists_celery.apply().get()
    first_completion = ShoppingListModel.objects.get(pk=stale.pk).completed_at

    second = archive_completed_lists_celery.apply().get()

    stale.refresh_from_db()
    assert stale.is_active is False
    assert ShoppingListModel.objects.get(pk=stale.pk).completed_at == first_completion
    assert second["archived"] == 0


# ---------------------------------------------------------------------------
# Wishlists
# ---------------------------------------------------------------------------


def test_a_stale_wishlist_is_archived() -> None:
    user = UserFactory()
    stale = _completed_wishlist(user, days_ago=8)

    result = archive_completed_lists_celery.apply().get()

    stale.refresh_from_db()
    assert stale.is_active is False
    assert result["wishlists_examined"] == 1


def test_a_recent_wishlist_is_left_alone() -> None:
    user = UserFactory()
    recent = _completed_wishlist(user, days_ago=5)

    archive_completed_lists_celery.apply().get()

    recent.refresh_from_db()
    assert recent.is_active is True


def test_both_kinds_of_list_are_swept_in_one_run() -> None:
    user = UserFactory()
    stale_list = _completed_list(user, days_ago=8)
    stale_wishlist = _completed_wishlist(user, days_ago=8)

    result = archive_completed_lists_celery.apply().get()

    stale_list.refresh_from_db()
    stale_wishlist.refresh_from_db()
    assert stale_list.is_active is False
    assert stale_wishlist.is_active is False
    assert result["archived"] == 2


# ---------------------------------------------------------------------------
# Idempotency and isolation
# ---------------------------------------------------------------------------


def test_the_sweep_is_idempotent_over_repeated_runs() -> None:
    user = UserFactory()
    _completed_list(user, days_ago=8)

    counts = [
        archive_completed_lists_celery.apply().get()["archived"] for _ in range(3)
    ]

    assert counts == [1, 0, 0]


def test_every_users_due_lists_are_swept_in_the_same_run() -> None:
    """The sweep is global: it reaches every user, not just the first."""
    first = _completed_list(UserFactory(), days_ago=8)
    second = _completed_list(UserFactory(), days_ago=8)

    archive_completed_lists_celery.apply().get()

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.is_active is False
    assert second.is_active is False


def test_a_list_restored_after_archiving_is_archived_again() -> None:
    """Restoring puts the list back in scope, and the sweep re-evaluates it."""
    user = UserFactory()
    stale = _completed_list(user, days_ago=8)
    archive_completed_lists_celery.apply().get()
    ShoppingListModel.objects.filter(pk=stale.pk).update(is_active=True)

    archive_completed_lists_celery.apply().get()

    stale.refresh_from_db()
    assert stale.is_active is False


def test_the_sweep_uses_the_clock_rather_than_a_hardcoded_now() -> None:
    """Freezing time must move the decision boundary, not be ignored."""
    user = UserFactory()
    boundary = _completed_list(user, days_ago=7)

    with mock.patch("apps.purchases.infrastructure.tasks.SystemClock") as clock_type:
        clock_type.return_value.now.return_value = timezone.now() + timedelta(days=1)
        archive_completed_lists_celery.apply().get()

    boundary.refresh_from_db()
    assert boundary.is_active is False
