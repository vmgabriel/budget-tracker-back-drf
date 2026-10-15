"""Module-specific defaults for the purchases context.

The domain layer carries no knowledge of default values; keeping them here
means an operator can retune archival behaviour without touching business
rules.
"""

from decimal import Decimal

PURCHASES_DEFAULTS: dict[str, Decimal] = {
    "ARCHIVE_DELAY_DAYS": Decimal("7.0"),
}
