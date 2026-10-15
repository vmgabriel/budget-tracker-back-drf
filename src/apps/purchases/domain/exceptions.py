"""Domain exceptions raised by purchases business rules."""


class PurchasesDomainError(Exception):
    """Base class for purchases domain failures."""


class ShoppingListNotFound(PurchasesDomainError):
    """Raised when a shopping list does not exist within the request scope."""


class WishlistNotFound(PurchasesDomainError):
    """Raised when a user has no wishlist within the request scope."""


class ShoppingListItemNotFound(PurchasesDomainError):
    """Raised when a shopping list item does not exist within the list."""


class WishlistItemNotFound(PurchasesDomainError):
    """Raised when a wishlist item does not exist within the wishlist."""


class TagNotFound(PurchasesDomainError):
    """Raised when a tag does not exist in the tag catalogue."""


class WishlistAlreadyExists(PurchasesDomainError):
    """Raised when a second wishlist is created for a user that already has one."""


class InvalidArchiveDelay(PurchasesDomainError):
    """Raised when the archival delay is not a usable number of days."""
