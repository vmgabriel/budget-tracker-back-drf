"""Celery tasks for the purchases context.

The archival sweep is the only scheduled work here. It is deliberately boring:
read the completed lists, ask the domain whether each one is stale, and hide
the ones that are.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from celery import shared_task
from django.db import OperationalError

from apps.purchases.application.ports.preferences import ArchiveDelayReader
from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.infrastructure.persistence.preferences import (
    ConfiguredArchiveDelayReader,
)
from apps.purchases.infrastructure.persistence.repositories import (
    DjangoShoppingListItemRepository,
    DjangoShoppingListRepository,
    DjangoWishlistItemRepository,
    DjangoWishlistRepository,
)
from shared.domain.ports.clock import Clock
from shared.infrastructure.clock import SystemClock

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ArchivalSweep:
    """Soft-delete every completed list whose archival delay has elapsed.

    Kept as a plain object rather than folded into the task body so it can be
    driven directly in tests with a fake clock and fake repositories.
    """

    shopping_lists: ShoppingListRepository
    shopping_list_items: ShoppingListItemRepository
    wishlists: WishlistRepository
    wishlist_items: WishlistItemRepository
    delays: ArchiveDelayReader
    clock: Clock

    def run(self) -> dict[str, int]:
        """Archive whatever is due and return the counts.

        The repositories are queried with ``now`` as the cutoff, not with the
        configured delay: that fetches every completed list and lets the
        domain apply each user's own delay. Filtering in SQL on one global
        delay would silently ignore any user who chose a shorter one.
        """
        now = self.clock.now()
        shopping_lists = self.shopping_lists.get_archived_candidates(now)
        wishlists = self.wishlists.get_archived_candidates(now)

        archived = self._archive_lists(shopping_lists, now)
        archived += self._archive_wishlists(wishlists, now)

        logger.info(
            "purchases archival finished shopping_lists=%s wishlists=%s "
            "archived=%s through=%s",
            len(shopping_lists),
            len(wishlists),
            archived,
            now.isoformat(),
        )
        return {
            "shopping_lists_examined": len(shopping_lists),
            "wishlists_examined": len(wishlists),
            "archived": archived,
        }

    def _archive_lists(self, shopping_lists: list[Any], now: datetime) -> int:
        archived = 0
        for shopping_list in shopping_lists:
            if shopping_list.id is None:
                continue
            # Completion is a claim about every item, and the candidate query
            # does not hydrate them. Without this the domain sees an empty
            # list, concludes nothing was bought, and archives nothing at all.
            shopping_list.items = self.shopping_list_items.get_by_list_id(
                shopping_list.id
            )
            delay = self.delays.get_archive_delay(shopping_list.user_id.value)
            if not shopping_list.should_archive(now, delay):
                continue
            self.shopping_lists.soft_delete(shopping_list.id)
            archived += 1
        return archived

    def _archive_wishlists(self, wishlists: list[Any], now: datetime) -> int:
        archived = 0
        for wishlist in wishlists:
            if wishlist.id is None:
                continue
            wishlist.items = self.wishlist_items.get_by_wishlist_id(wishlist.id)
            delay = self.delays.get_archive_delay(wishlist.user_id.value)
            if not wishlist.should_archive(now, delay):
                continue
            self.wishlists.soft_delete(wishlist.id)
            archived += 1
        return archived


@shared_task(
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
)
def archive_completed_lists_celery(self: Any) -> dict[str, int]:
    """Archive completed shopping lists and wishlists past their delay.

    Idempotent by construction: the sweep only ever reads lists that are still
    active, and the write is a one-way flag. A retry after a partial run
    archives whatever the first attempt missed and touches nothing twice.
    """
    sweep = ArchivalSweep(
        shopping_lists=DjangoShoppingListRepository(),
        shopping_list_items=DjangoShoppingListItemRepository(),
        wishlists=DjangoWishlistRepository(),
        wishlist_items=DjangoWishlistItemRepository(),
        delays=ConfiguredArchiveDelayReader(),
        clock=SystemClock(),
    )
    return sweep.run()
