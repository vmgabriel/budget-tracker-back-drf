"""Domain exceptions raised by transaction business rules."""


class TransactionDomainError(Exception):
    """Base class for transaction domain failures."""


class FutureTransactionDate(TransactionDomainError):
    """Raised when a transaction is dated after the current day."""


class TransactionNotFound(TransactionDomainError):
    """Raised when a transaction does not exist for the requesting owner."""


class AccountNotFound(TransactionDomainError):
    """Raised when a funding account does not exist for the requesting owner."""


class InvalidAccountType(TransactionDomainError):
    """Raised when a funding account is built with an unsupported type."""
