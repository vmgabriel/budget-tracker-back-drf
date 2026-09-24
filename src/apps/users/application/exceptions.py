"""Application errors that do not belong to the domain model."""


class UserApplicationError(Exception):
    """Base class for user use-case failures."""


class InvalidUserInput(UserApplicationError):
    """Raised when a use-case command violates application policy."""


class AuthenticationFailed(UserApplicationError):
    """Raised when credentials cannot establish a user session."""
