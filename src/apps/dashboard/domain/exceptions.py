"""Domain exceptions raised by dashboard business rules."""


class DashboardDomainError(Exception):
    """Base class for dashboard domain failures."""


class DashboardSummaryImmutable(DashboardDomainError):
    """Raised when a fresh, closed-period summary is modified."""


class InvalidDashboardSummary(DashboardDomainError):
    """Raised when a dashboard summary aggregate is inconsistent."""
