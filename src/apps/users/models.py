"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.users.infrastructure.persistence.models import User

__all__ = ("User",)
