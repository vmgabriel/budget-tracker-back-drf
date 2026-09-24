"""Shared port for time abstraction."""

from datetime import date, datetime
from typing import Protocol


class Clock(Protocol):
    """Abstract time source for deterministic domain behavior.

    Domain code should depend on this protocol rather than calling
    ``datetime.now()`` directly, allowing frozen clocks in tests.
    """

    def now(self) -> datetime:
        """Return the current timezone-aware datetime."""
        ...

    def today(self) -> date:
        """Return the current date."""
        ...
