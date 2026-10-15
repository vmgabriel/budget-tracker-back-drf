"""Application errors that do not belong to the purchases domain model."""


class PurchasesApplicationError(Exception):
    """Base class for purchases use-case failures."""


class InvalidPurchasesInput(PurchasesApplicationError):
    """Raised when a command violates application or domain policy."""
