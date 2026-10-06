"""Domain exceptions raised by tasks business rules."""


class TasksDomainError(Exception):
    """Base class for tasks domain failures."""


class TaskNotFound(TasksDomainError):
    """Raised when a task does not exist for the requesting owner."""


class GoalNotFound(TasksDomainError):
    """Raised when a goal does not exist for the requesting owner."""


class DailyPlanNotFound(TasksDomainError):
    """Raised when a daily plan does not exist within the request scope."""


class InvalidDuration(TasksDomainError):
    """Raised when an hour estimate breaks a duration invariant."""


class InvalidThreshold(TasksDomainError):
    """Raised when a planning threshold breaks a duration invariant."""


class TaskAlreadyDone(TasksDomainError):
    """Raised when a transition is requested on an already completed task."""


class TaskAlreadyInPlan(TasksDomainError):
    """Raised when a task is scheduled twice on the same daily plan."""


class DailyPlanFull(TasksDomainError):
    """Raised when a task would be scheduled beyond the daily hour budget."""
