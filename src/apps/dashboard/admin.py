"""Django admin discovery shim; registration lives in infrastructure."""

from apps.dashboard.infrastructure.admin import DashboardSummaryAdmin

__all__ = ("DashboardSummaryAdmin",)
