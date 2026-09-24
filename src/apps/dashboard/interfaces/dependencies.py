"""Composition of dashboard query use cases and infrastructure adapters."""

from dataclasses import dataclass

from apps.dashboard.application.use_cases import (
    GetDashboardOverview,
    GetUserDashboard,
)
from apps.dashboard.infrastructure.persistence.repositories import (
    DjangoDashboardSummaryRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class DashboardUseCases:
    """Dashboard query use cases sharing one persistence adapter."""

    get: GetUserDashboard
    overview: GetDashboardOverview


def build_dashboard_use_cases() -> DashboardUseCases:
    """Build dashboard use cases with infrastructure dependencies."""
    repository = DjangoDashboardSummaryRepository()
    clock = SystemClock()
    return DashboardUseCases(
        get=GetUserDashboard(repository, clock),
        overview=GetDashboardOverview(repository, clock),
    )
