"""Django admin discovery shim; registration lives in infrastructure."""

from apps.transactions.infrastructure.admin import AccountAdmin, TransactionAdmin

__all__ = ("AccountAdmin", "TransactionAdmin")
