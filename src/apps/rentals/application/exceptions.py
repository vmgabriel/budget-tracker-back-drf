"""Application errors that do not belong to the rentals domain model."""


class RentalsApplicationError(Exception):
    """Base class for rentals use-case failures."""


class InvalidRentalsInput(RentalsApplicationError):
    """Raised when a command violates application or domain policy."""
