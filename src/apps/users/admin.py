"""Django admin discovery shim; registration lives in infrastructure."""

from apps.users.infrastructure.admin import UserAdmin

__all__ = ("UserAdmin",)
