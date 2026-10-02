"""Domain exceptions raised by profile business rules."""


class ProfileDomainError(Exception):
    """Base class for profile domain failures."""


class ProfileNotFound(ProfileDomainError):
    """Raised when a profile does not exist for the requesting user."""


class InvalidTimezone(ProfileDomainError):
    """Raised when a timezone is not a valid IANA timezone name."""


class InvalidLanguage(ProfileDomainError):
    """Raised when a language is not a valid ISO 639-1 code."""


class InvalidCurrency(ProfileDomainError):
    """Raised when a currency is not a valid ISO 4217 code."""


class BioTooLong(ProfileDomainError):
    """Raised when a bio exceeds the maximum allowed length."""
