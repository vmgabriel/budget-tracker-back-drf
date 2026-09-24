"""Clock port for deterministic transaction behavior."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Provides the current timezone-aware time."""

    def now(self) -> datetime:
        """Return the current time."""
        raise NotImplementedError()
