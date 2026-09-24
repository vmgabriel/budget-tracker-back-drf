"""Application errors that do not belong to the transaction domain model."""


class TransactionApplicationError(Exception):
    """Base class for transaction use-case failures."""


class InvalidTransactionInput(TransactionApplicationError):
    """Raised when a transaction command violates application policy."""
