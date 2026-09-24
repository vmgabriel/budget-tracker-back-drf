"""Dashboard application-layer exceptions."""


class InvalidDashboardQuery(Exception):
    """Raised when a dashboard date range cannot be served."""


class InvalidDashboardCommand(Exception):
    """Raised when a summary generation command is inconsistent."""
