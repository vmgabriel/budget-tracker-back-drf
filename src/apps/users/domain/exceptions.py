"""Domain exceptions raised by user business rules."""


class UserDomainError(Exception):
    """Base class for user domain failures."""


class EmailAlreadyExists(UserDomainError):
    """Raised when an email is already assigned to a user."""


class UserNotFound(UserDomainError):
    """Raised when a requested user does not exist."""
