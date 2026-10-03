"""Domain exceptions raised by rentals business rules."""


class RentalsDomainError(Exception):
    """Base class for rental domain failures."""


class HouseNotFound(RentalsDomainError):
    """Raised when a house does not exist for the requesting owner."""


class ApartmentNotFound(RentalsDomainError):
    """Raised when an apartment does not exist within the request scope."""


class DocumentNotFound(RentalsDomainError):
    """Raised when a document does not exist within the request scope."""


class PaymentRecordNotFound(RentalsDomainError):
    """Raised when a payment record does not exist within the request scope."""


class UtilityReadingNotFound(RentalsDomainError):
    """Raised when a utility reading does not exist within the request scope."""


class InvalidReading(RentalsDomainError):
    """Raised when a meter reading breaks a measurement invariant."""


class InvalidPaymentAmount(RentalsDomainError):
    """Raised when a payment amount breaks a financial invariant."""


class InvalidAddress(RentalsDomainError):
    """Raised when a property address is malformed or incomplete."""
