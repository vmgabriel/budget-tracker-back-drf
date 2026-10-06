"""Django ORM implementation of the tasks repository ports.

Repositories are the only place that translates between aggregates and rows.
They hold no business rules: validation and state transitions already happened
in the domain, so ``_to_domain`` and ``_to_model`` are symmetric and lossless.
"""

from collections.abc import Sequence
from datetime import date

from django.db import transaction as db_transaction

from apps.tasks.application.ports.repositories import (
    DailyPlanRepository,
    GoalRepository,
    TaskRepository,
)
from apps.tasks.domain.entities import DailyPlan, Goal, Task
from apps.tasks.domain.exceptions import (
    DailyPlanNotFound,
    GoalNotFound,
    TaskNotFound,
)
from apps.tasks.domain.value_objects import (
    DailyPlanId,
    Duration,
    GoalId,
    GoalStatus,
    Priority,
    TaskId,
    TaskStatus,
    UserId,
)
from apps.tasks.infrastructure.persistence.models import (
    DailyPlanModel,
    GoalModel,
    TaskModel,
)

TASK_UPDATE_FIELDS = (
    "goal",
    "name",
    "description",
    "due_date",
    "importance",
    "estimated_hours",
    "status",
    "is_checked_by_llm",
    "llm_evaluation_failed",
    "updated_at",
)

GOAL_UPDATE_FIELDS = (
    "name",
    "description",
    "due_date",
    "status",
    "updated_at",
)


class DjangoTaskRepository(TaskRepository):
    """Persist and retrieve task aggregates with the Django ORM."""

    def get_by_id(self, task_id: TaskId) -> Task | None:
        model = TaskModel.objects.filter(pk=task_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_ids(self, task_ids: Sequence[TaskId]) -> list[Task]:
        identifiers = [task_id.value for task_id in task_ids]
        if not identifiers:
            return []
        models = TaskModel.objects.filter(pk__in=identifiers)
        return [self._to_domain(model) for model in models]

    def get_by_user_id(self, user_id: UserId) -> list[Task]:
        models = TaskModel.objects.filter(user_id=user_id.value)
        return [self._to_domain(model) for model in models]

    def get_by_goal_id(self, goal_id: GoalId) -> list[Task]:
        models = TaskModel.objects.filter(goal_id=goal_id.value)
        return [self._to_domain(model) for model in models]

    def save(self, task: Task) -> Task:
        model = self._to_model(task)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, task: Task) -> Task:
        if task.id is None:
            raise ValueError("A persisted task must have an identity.")
        model = TaskModel.objects.filter(pk=task.id.value).first()
        if model is None:
            raise TaskNotFound("Task not found.")
        self._apply_to_model(model, task)
        with db_transaction.atomic():
            model.save(update_fields=TASK_UPDATE_FIELDS)
        return self._to_domain(model)

    def delete(self, task: Task) -> None:
        if task.id is None:
            raise ValueError("A persisted task must have an identity.")
        deleted, _ = TaskModel.objects.filter(pk=task.id.value).delete()
        if not deleted:
            raise TaskNotFound("Task not found.")

    @staticmethod
    def _to_model(task: Task) -> TaskModel:
        return TaskModel(
            id=task.id.value if task.id is not None else None,
            user_id=task.user_id.value,
            goal_id=task.goal_id.value if task.goal_id is not None else None,
            name=task.name,
            description=task.description,
            due_date=task.due_date,
            importance=task.importance.value,
            estimated_hours=task.estimated_hours.hours,
            status=task.status.value,
            is_checked_by_llm=task.is_checked_by_llm,
            llm_evaluation_failed=task.llm_evaluation_failed,
        )

    @staticmethod
    def _apply_to_model(model: TaskModel, task: Task) -> None:
        model.goal_id = task.goal_id.value if task.goal_id is not None else None
        model.name = task.name
        model.description = task.description
        model.due_date = task.due_date
        model.importance = task.importance.value
        model.estimated_hours = task.estimated_hours.hours
        model.status = task.status.value
        model.is_checked_by_llm = task.is_checked_by_llm
        model.llm_evaluation_failed = task.llm_evaluation_failed

    @staticmethod
    def _to_domain(model: TaskModel) -> Task:
        return Task(
            id=TaskId(model.id),
            goal_id=GoalId(model.goal_id) if model.goal_id is not None else None,
            user_id=UserId(model.user_id),
            name=model.name,
            description=model.description,
            due_date=model.due_date,
            importance=Priority(model.importance),
            estimated_hours=Duration(model.estimated_hours),
            status=TaskStatus(model.status),
            is_checked_by_llm=model.is_checked_by_llm,
            llm_evaluation_failed=model.llm_evaluation_failed,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DjangoGoalRepository(GoalRepository):
    """Persist and retrieve goal aggregates with the Django ORM."""

    def get_by_id(self, goal_id: GoalId) -> Goal | None:
        model = GoalModel.objects.filter(pk=goal_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_user_id(self, user_id: UserId) -> list[Goal]:
        models = GoalModel.objects.filter(user_id=user_id.value)
        return [self._to_domain(model) for model in models]

    def save(self, goal: Goal) -> Goal:
        model = self._to_model(goal)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, goal: Goal) -> Goal:
        if goal.id is None:
            raise ValueError("A persisted goal must have an identity.")
        model = GoalModel.objects.filter(pk=goal.id.value).first()
        if model is None:
            raise GoalNotFound("Goal not found.")
        model.name = goal.name
        model.description = goal.description
        model.due_date = goal.due_date
        model.status = goal.status.value
        with db_transaction.atomic():
            model.save(update_fields=GOAL_UPDATE_FIELDS)
        return self._to_domain(model)

    def delete(self, goal: Goal) -> None:
        if goal.id is None:
            raise ValueError("A persisted goal must have an identity.")
        deleted, _ = GoalModel.objects.filter(pk=goal.id.value).delete()
        if not deleted:
            raise GoalNotFound("Goal not found.")

    @staticmethod
    def _to_model(goal: Goal) -> GoalModel:
        return GoalModel(
            id=goal.id.value if goal.id is not None else None,
            user_id=goal.user_id.value,
            name=goal.name,
            description=goal.description,
            due_date=goal.due_date,
            status=goal.status.value,
        )

    @staticmethod
    def _to_domain(model: GoalModel) -> Goal:
        return Goal(
            id=GoalId(model.id),
            user_id=UserId(model.user_id),
            name=model.name,
            description=model.description,
            due_date=model.due_date,
            status=GoalStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class DjangoDailyPlanRepository(DailyPlanRepository):
    """Persist and retrieve daily plan aggregates with the Django ORM.

    The scheduled tasks are a plain many-to-many relation, so storage does not
    remember the order they were added in: a day is rebuilt newest-task-first.
    If per-day ordering ever becomes a requirement, the relation needs an
    explicit position column rather than a bigger in-memory sort.
    """

    def get_by_id(self, plan_id: DailyPlanId) -> DailyPlan | None:
        model = DailyPlanModel.objects.filter(pk=plan_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_user_and_date(self, user_id: UserId, day: date) -> DailyPlan | None:
        model = DailyPlanModel.objects.filter(
            user_id=user_id.value,
            date=day,
        ).first()
        return self._to_domain(model) if model is not None else None

    def get_by_user_and_date_range(
        self, user_id: UserId, start_date: date, end_date: date
    ) -> list[DailyPlan]:
        models = DailyPlanModel.objects.filter(
            user_id=user_id.value,
            date__gte=start_date,
            date__lte=end_date,
        )
        return [self._to_domain(model) for model in models]

    def save(self, plan: DailyPlan) -> DailyPlan:
        model = self._to_model(plan)
        with db_transaction.atomic():
            model.save(force_insert=True)
            self._sync_tasks(model, plan)
        return self._to_domain(model)

    def update(self, plan: DailyPlan) -> DailyPlan:
        if plan.id is None:
            raise ValueError("A persisted daily plan must have an identity.")
        model = DailyPlanModel.objects.filter(pk=plan.id.value).first()
        if model is None:
            raise DailyPlanNotFound("Daily plan not found.")
        model.total_hours = plan.total_hours.hours
        model.generated_by_llm = plan.generated_by_llm
        with db_transaction.atomic():
            model.save(update_fields=("total_hours", "generated_by_llm", "updated_at"))
        self._sync_tasks(model, plan)
        return self._to_domain(model)

    def delete(self, plan: DailyPlan) -> None:
        if plan.id is None:
            raise ValueError("A persisted daily plan must have an identity.")
        deleted, _ = DailyPlanModel.objects.filter(pk=plan.id.value).delete()
        if not deleted:
            raise DailyPlanNotFound("Daily plan not found.")

    @staticmethod
    def _to_model(plan: DailyPlan) -> DailyPlanModel:
        return DailyPlanModel(
            id=plan.id.value if plan.id is not None else None,
            user_id=plan.user_id.value,
            date=plan.date,
            total_hours=plan.total_hours.hours,
            generated_by_llm=plan.generated_by_llm,
        )

    @staticmethod
    def _sync_tasks(model: DailyPlanModel, plan: DailyPlan) -> None:
        scheduled = TaskModel.objects.filter(
            pk__in=[task_id.value for task_id in plan.task_ids]
        )
        model.tasks.set(list(scheduled))

    @staticmethod
    def _to_domain(model: DailyPlanModel) -> DailyPlan:
        return DailyPlan(
            id=DailyPlanId(model.id),
            user_id=UserId(model.user_id),
            date=model.date,
            task_ids=[
                TaskId(task_id)
                for task_id in model.tasks.order_by("-created_at", "-id").values_list(
                    "id", flat=True
                )
            ],
            total_hours=Duration(model.total_hours),
            generated_by_llm=model.generated_by_llm,
            created_at=model.created_at,
        )
