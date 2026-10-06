"""Task, goal, and daily plan aggregates with their business rules."""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from apps.tasks.domain.exceptions import (
    DailyPlanFull,
    DailyPlanNotFound,
    TaskAlreadyDone,
    TaskAlreadyInPlan,
)
from apps.tasks.domain.value_objects import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    CalendarDate,
    DailyPlanId,
    Duration,
    GoalId,
    GoalStatus,
    OverwhelmedThreshold,
    Priority,
    TaskId,
    TaskStatus,
    UserId,
    normalize_date,
    normalize_description,
    normalize_text,
)

ZERO_HOURS = Duration(Decimal("0.00"))


@dataclass(eq=False, slots=True)
class Task:
    """One owner-scoped unit of work, optionally part of a goal."""

    user_id: UserId
    name: str
    description: str
    importance: Priority
    estimated_hours: Duration
    created_at: datetime
    updated_at: datetime
    id: TaskId | None = None
    goal_id: GoalId | None = None
    due_date: date | None = None
    status: TaskStatus = TaskStatus.TODO
    is_checked_by_llm: bool = False
    llm_evaluation_failed: bool = False

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        name: str,
        description: str,
        importance: Priority,
        estimated_hours: Duration,
        now: datetime,
        goal_id: GoalId | None = None,
        due_date: date | None = None,
        status: TaskStatus = TaskStatus.TODO,
    ) -> "Task":
        """Create a task after validating aggregate invariants."""
        cls._validate_owner(user_id)
        cls._validate_importance(importance)
        cls._validate_estimated_hours(estimated_hours)
        cls._validate_status(status)
        cls._validate_goal_id(goal_id)
        due_date = normalize_date(due_date, label="Task due date")
        _require_aware(now, "Task timestamps must be timezone-aware.")
        return cls(
            id=None,
            goal_id=goal_id,
            user_id=user_id,
            name=normalize_text(name, label="Task name", limit=MAX_NAME_LENGTH),
            description=normalize_description(
                description, limit=MAX_DESCRIPTION_LENGTH
            ),
            due_date=due_date,
            importance=importance,
            estimated_hours=estimated_hours,
            status=status,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str,
        description: str,
        importance: Priority,
        estimated_hours: Duration,
        due_date: date | None,
        now: datetime,
    ) -> None:
        """Apply a validated replacement to the editable task fields."""
        _require_aware(now, "Task timestamps must be timezone-aware.")
        self._validate_importance(importance)
        self._validate_estimated_hours(estimated_hours)
        normalized_date = normalize_date(due_date, label="Task due date")
        normalized_name = normalize_text(name, label="Task name", limit=MAX_NAME_LENGTH)
        normalized_description = normalize_description(
            description, limit=MAX_DESCRIPTION_LENGTH
        )
        content_changed = (
            normalized_name != self.name
            or normalized_description != self.description
            or normalized_date != self.due_date
        )
        self.name = normalized_name
        self.description = normalized_description
        self.due_date = normalized_date
        self.importance = importance
        self.estimated_hours = estimated_hours
        if content_changed:
            # The stored content no longer matches what was evaluated, so the
            # task must be re-checked before the LLM insights can be trusted.
            self.is_checked_by_llm = False
        self.updated_at = now

    def is_overwhelmed(self, threshold: OverwhelmedThreshold) -> bool:
        """Return whether the estimate surpasses the caller's threshold."""
        if not isinstance(threshold, OverwhelmedThreshold):
            raise TypeError("Threshold must be an OverwhelmedThreshold.")
        return threshold.is_exceeded_by(self.estimated_hours)

    def mark_as_doing(self, *, now: datetime) -> None:
        """Start the task; a completed task cannot be reopened silently."""
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyDone("A completed task cannot be moved back to doing.")
        _require_aware(now, "Task timestamps must be timezone-aware.")
        self.status = TaskStatus.DOING
        self.updated_at = now

    def mark_as_done(self, *, now: datetime) -> None:
        """Complete the task."""
        if self.status is TaskStatus.DONE:
            raise TaskAlreadyDone("Task is already marked as done.")
        _require_aware(now, "Task timestamps must be timezone-aware.")
        self.status = TaskStatus.DONE
        self.updated_at = now

    def promote_priority(self, *, now: datetime) -> Priority:
        """Raise importance by one level, saturating at ``high``."""
        _require_aware(now, "Task timestamps must be timezone-aware.")
        promoted = self.importance.promote()
        self.importance = promoted
        self.updated_at = now
        return promoted

    def link_to_goal(self, goal_id: GoalId, *, now: datetime) -> None:
        """Associate the task with a goal."""
        if not isinstance(goal_id, GoalId):
            raise TypeError("Task goal must be identified by a GoalId.")
        _require_aware(now, "Task timestamps must be timezone-aware.")
        self.goal_id = goal_id
        self.updated_at = now

    def unlink_from_goal(self, *, now: datetime) -> None:
        """Detach the task from its goal, keeping the task itself."""
        _require_aware(now, "Task timestamps must be timezone-aware.")
        self.goal_id = None
        self.updated_at = now

    def mark_llm_checked(self) -> None:
        """Record that the current content was successfully evaluated."""
        self.is_checked_by_llm = True
        self.llm_evaluation_failed = False

    def flag_llm_evaluation_failed(self) -> None:
        """Record that evaluation of the current content failed."""
        self.llm_evaluation_failed = True

    @property
    def needs_llm_evaluation(self) -> bool:
        """Return whether the task awaits a fresh LLM evaluation."""
        return not self.is_checked_by_llm or self.llm_evaluation_failed

    @classmethod
    def _validate_owner(cls, user_id: UserId) -> None:
        if not isinstance(user_id, UserId):
            raise TypeError("Task owner must be a UserId.")

    @staticmethod
    def _validate_importance(importance: Priority) -> None:
        if not isinstance(importance, Priority):
            raise ValueError("Task importance is invalid.")

    @staticmethod
    def _validate_estimated_hours(estimated_hours: Duration) -> None:
        if not isinstance(estimated_hours, Duration):
            raise TypeError("Task estimate must be a Duration.")

    @staticmethod
    def _validate_status(status: TaskStatus) -> None:
        if not isinstance(status, TaskStatus):
            raise ValueError("Task status is invalid.")

    @staticmethod
    def _validate_goal_id(goal_id: GoalId | None) -> None:
        if goal_id is not None and not isinstance(goal_id, GoalId):
            raise TypeError("Task goal must be identified by a GoalId.")


@dataclass(eq=False, slots=True)
class Goal:
    """A macrotask grouping several tasks under a shared outcome."""

    user_id: UserId
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    id: GoalId | None = None
    due_date: date | None = None
    status: GoalStatus = GoalStatus.ACTIVE

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        name: str,
        description: str,
        now: datetime,
        due_date: date | None = None,
        status: GoalStatus = GoalStatus.ACTIVE,
    ) -> "Goal":
        """Create a goal after validating aggregate invariants."""
        if not isinstance(user_id, UserId):
            raise TypeError("Goal owner must be a UserId.")
        if not isinstance(status, GoalStatus):
            raise ValueError("Goal status is invalid.")
        due_date = normalize_date(due_date, label="Goal due date")
        _require_aware(now, "Goal timestamps must be timezone-aware.")
        return cls(
            id=None,
            user_id=user_id,
            name=normalize_text(name, label="Goal name", limit=MAX_NAME_LENGTH),
            description=normalize_description(
                description, limit=MAX_DESCRIPTION_LENGTH
            ),
            due_date=due_date,
            status=status,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        *,
        name: str,
        description: str,
        due_date: date | None,
        now: datetime,
    ) -> None:
        """Apply a validated replacement to the editable goal fields."""
        _require_aware(now, "Goal timestamps must be timezone-aware.")
        normalized_date = normalize_date(due_date, label="Goal due date")
        self.name = normalize_text(name, label="Goal name", limit=MAX_NAME_LENGTH)
        self.description = normalize_description(
            description, limit=MAX_DESCRIPTION_LENGTH
        )
        self.due_date = normalized_date
        self.updated_at = now

    def mark_as_completed(self, *, now: datetime) -> None:
        """Mark the goal as reached."""
        _require_aware(now, "Goal timestamps must be timezone-aware.")
        self.status = GoalStatus.COMPLETED
        self.updated_at = now

    def mark_as_archived(self, *, now: datetime) -> None:
        """Move the goal out of the active set without deleting it."""
        _require_aware(now, "Goal timestamps must be timezone-aware.")
        self.status = GoalStatus.ARCHIVED
        self.updated_at = now

    def reactivate(self, *, now: datetime) -> None:
        """Return an archived or completed goal to the active set."""
        _require_aware(now, "Goal timestamps must be timezone-aware.")
        self.status = GoalStatus.ACTIVE
        self.updated_at = now


@dataclass(eq=False, slots=True)
class DailyPlan:
    """The set of tasks scheduled for one owner on one calendar day."""

    user_id: UserId
    date: CalendarDate
    created_at: datetime
    id: DailyPlanId | None = None
    task_ids: list[TaskId] = field(default_factory=list)
    total_hours: Duration = ZERO_HOURS
    generated_by_llm: bool = False

    @classmethod
    def create(
        cls,
        *,
        user_id: UserId,
        date: CalendarDate,
        now: datetime,
        generated_by_llm: bool = False,
    ) -> "DailyPlan":
        """Create an empty daily plan."""
        if not isinstance(user_id, UserId):
            raise TypeError("Daily plan owner must be a UserId.")
        plan_date = normalize_date(date, label="Daily plan date")
        if plan_date is None:
            raise ValueError("Daily plan date must be a date.")
        _require_aware(now, "Daily plan timestamps must be timezone-aware.")
        return cls(
            id=None,
            user_id=user_id,
            date=plan_date,
            task_ids=[],
            total_hours=ZERO_HOURS,
            generated_by_llm=generated_by_llm,
            created_at=now,
        )

    def contains(self, task_id: TaskId) -> bool:
        """Return whether the task is already scheduled on this day."""
        return task_id in self.task_ids

    def is_full(self, max_hours: Duration) -> bool:
        """Return whether the day has reached its hour budget."""
        if not isinstance(max_hours, Duration):
            raise TypeError("Daily plan budget must be a Duration.")
        return self.total_hours.hours >= max_hours.hours

    def add_task(
        self,
        task_id: TaskId,
        task_hours: Duration,
        *,
        max_hours: Duration | None = None,
    ) -> None:
        """Schedule a task, optionally refusing to exceed ``max_hours``."""
        if not isinstance(task_id, TaskId):
            raise TypeError("Daily plan task must be identified by a TaskId.")
        if not isinstance(task_hours, Duration):
            raise TypeError("Task hours must be a Duration.")
        if task_id in self.task_ids:
            raise TaskAlreadyInPlan("Task is already scheduled on this day.")
        if max_hours is not None and self.is_full(max_hours):
            raise DailyPlanFull("Daily plan has no remaining hours available.")
        self.task_ids.append(task_id)
        self.total_hours = self.total_hours + task_hours

    def remove_task(self, task_id: TaskId, task_hours: Duration) -> None:
        """Unschedule a task and give its hours back to the day."""
        if not isinstance(task_id, TaskId):
            raise TypeError("Daily plan task must be identified by a TaskId.")
        if not isinstance(task_hours, Duration):
            raise TypeError("Task hours must be a Duration.")
        try:
            self.task_ids.remove(task_id)
        except ValueError as error:
            raise DailyPlanNotFound("Task is not scheduled on this day.") from error
        self.total_hours = self.total_hours - task_hours

    def mark_as_llm_generated(self) -> None:
        """Record that the day was proposed by the assistant."""
        self.generated_by_llm = True


def _require_aware(now: datetime, message: str) -> None:
    if not isinstance(now, datetime):
        raise TypeError("Timestamp must be a datetime.")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(message)
