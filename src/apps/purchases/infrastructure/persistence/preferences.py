"""Adapters that resolve preferences purchases does not itself own."""

from decimal import Decimal, InvalidOperation
from uuid import UUID

from apps.purchases.application.config import PURCHASES_DEFAULTS
from apps.purchases.application.ports.preferences import ArchiveDelayReader
from apps.purchases.domain.exceptions import InvalidArchiveDelay
from apps.purchases.domain.value_objects import ArchiveDelay


class ConfiguredArchiveDelayReader(ArchiveDelayReader):
    """Serve the context-wide archival delay to every user.

    There is no per-user archive delay stored anywhere yet, so this adapter
    answers with ``PURCHASES_DEFAULTS``. It exists as a seam: when the setting
    becomes a real user preference, this is the single place that changes, and
    the task keeps working unchanged either way.
    """

    def __init__(self, default_days: Decimal | None = None) -> None:
        self._days = (
            PURCHASES_DEFAULTS["ARCHIVE_DELAY_DAYS"]
            if default_days is None
            else default_days
        )

    def get_archive_delay(self, user_id: UUID) -> ArchiveDelay:
        return self._resolve(self._days)

    @staticmethod
    def _resolve(days: object) -> ArchiveDelay:
        """Coerce a stored value into an ``ArchiveDelay``.

        A corrupt preference must not stop the sweep: the whole point of a
        fallback is that a bad value still archives on the documented default
        rather than raising out of a periodic job.
        """
        try:
            return ArchiveDelay(days)  # type: ignore[arg-type]
        except (InvalidArchiveDelay, InvalidOperation, TypeError, ValueError):
            return ArchiveDelay(PURCHASES_DEFAULTS["ARCHIVE_DELAY_DAYS"])
