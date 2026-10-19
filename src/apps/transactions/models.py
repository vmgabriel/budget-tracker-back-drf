"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.transactions.infrastructure.persistence.models import Account, Transaction

__all__ = ("Account", "Transaction")
