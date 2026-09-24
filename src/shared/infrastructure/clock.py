"""Shared infrastructure implementations."""

from datetime import UTC, date, datetime

from shared.domain.ports.clock import Clock


class SystemClock(Clock):
    """Provide timezone-aware UTC timestamps using the system clock.

    This is the production implementation. Tests can inject frozen clocks for
    deterministic behavior.
    """

    def now(self) -> datetime:
        """Return the current UTC datetime."""
        return datetime.now(UTC)

    def today(self) -> date:
        """Return the current UTC date."""
        return datetime.now(UTC).date()
