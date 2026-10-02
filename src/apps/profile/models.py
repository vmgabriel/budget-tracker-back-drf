"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.profile.infrastructure.persistence.models import ProfileModel

__all__ = ("ProfileModel",)
