"""System clock adapter for transaction use cases."""

from datetime import UTC, datetime

from apps.transactions.application.ports.clock import Clock


class SystemClock(Clock):
    """Provide timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        return datetime.now(UTC)
