"""Application errors that do not belong to the tasks domain model.

Only *validation* failures are translated here. Domain outcomes such as
``DailyPlanFull`` or ``TaskAlreadyDone`` deliberately travel untouched so the
interface layer can map them to a distinct status code instead of collapsing
every business rejection into a generic 400.
"""


class TasksApplicationError(Exception):
    """Base class for tasks use-case failures."""


class InvalidTasksInput(TasksApplicationError):
    """Raised when a tasks command violates application or domain policy."""
