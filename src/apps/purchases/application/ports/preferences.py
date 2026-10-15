"""Ports for reading user preferences that purchases does not own."""

from typing import Protocol
from uuid import UUID

from apps.purchases.domain.value_objects import ArchiveDelay


class ArchiveDelayReader(Protocol):
    """Read the number of days a user's completed lists stay active.

    The delay is a user preference, but it is not stored in the purchases
    context, so purchases depends on this port rather than on another
    context's model. An adapter resolves it from wherever it actually lives.
    """

    def get_archive_delay(self, user_id: UUID) -> ArchiveDelay:
        """Return the user's archival delay, or the configured default."""
        ...
