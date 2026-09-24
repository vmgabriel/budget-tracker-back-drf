"""Django admin discovery shim; registration lives in infrastructure."""

from apps.transactions.infrastructure.admin import TransactionAdmin

__all__ = ("TransactionAdmin",)
