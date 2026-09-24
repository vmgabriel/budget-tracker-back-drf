"""Dashboard application use cases and dependency-inversion ports."""

from apps.dashboard.application.dto import DashboardData, DashboardOverview
from apps.dashboard.application.exceptions import (
    InvalidDashboardCommand,
    InvalidDashboardQuery,
)
from apps.dashboard.application.ports import (
    Clock,
    DashboardSummaryRepository,
    TransactionRepository,
)
from apps.dashboard.application.use_cases import (
    GenerateDashboardSummary,
    GenerateDashboardSummaryCommand,
    GetDashboardOverview,
    GetUserDashboard,
    GetUserDashboardCommand,
    InvalidateUserCache,
    InvalidateUserCacheCommand,
)

__all__ = (
    "Clock",
    "DashboardData",
    "DashboardOverview",
    "DashboardSummaryRepository",
    "GenerateDashboardSummary",
    "GenerateDashboardSummaryCommand",
    "GetDashboardOverview",
    "GetUserDashboard",
    "GetUserDashboardCommand",
    "InvalidDashboardCommand",
    "InvalidDashboardQuery",
    "InvalidateUserCache",
    "InvalidateUserCacheCommand",
    "TransactionRepository",
)
