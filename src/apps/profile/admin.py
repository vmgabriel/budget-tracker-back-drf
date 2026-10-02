"""Django admin discovery shim; registration lives in infrastructure."""

from apps.profile.infrastructure.admin import ProfileModelAdmin

__all__ = ("ProfileModelAdmin",)
