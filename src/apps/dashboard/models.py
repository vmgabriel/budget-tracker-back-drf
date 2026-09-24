"""Django model discovery shim; ORM definitions remain in infrastructure."""

from apps.dashboard.infrastructure.persistence.models import DashboardSummary

__all__ = ("DashboardSummary",)
