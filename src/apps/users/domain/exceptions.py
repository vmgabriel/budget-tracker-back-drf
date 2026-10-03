"""Domain exceptions raised by user business rules."""


class UserDomainError(Exception):
    """Base class for user domain failures."""


class EmailAlreadyExists(UserDomainError):
    """Raised when an email is already assigned to a user."""


class UserNotFound(UserDomainError):
    """Raised when a requested user does not exist."""


class UserAlreadyBanned(UserDomainError):
    """Raised when a banned user is banned again."""


class UserNotBanned(UserDomainError):
    """Raised when an active user is unbanned."""
