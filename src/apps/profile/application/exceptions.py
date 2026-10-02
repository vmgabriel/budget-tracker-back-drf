"""Application errors that do not belong to the profile domain model."""


class ProfileApplicationError(Exception):
    """Base class for profile use-case failures."""


class InvalidProfileInput(ProfileApplicationError):
    """Raised when a profile command violates application policy."""
