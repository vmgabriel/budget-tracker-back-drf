"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.transactions.infrastructure.persistence.models import Transaction

__all__ = ("Transaction",)
