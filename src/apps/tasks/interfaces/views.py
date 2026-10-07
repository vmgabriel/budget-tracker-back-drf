"""HTTP controllers for the tasks bounded context.

Views stay thin: validate the payload, build a command, call one use case, and
serialize its result. Ownership is enforced inside the use cases, so a resource
belonging to somebody else answers 404 exactly like a missing one.
"""

from typing import Any
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.tasks.application.commands import (
    UNSET,
    AddTaskToDailyPlanCommand,
    CreateGoalCommand,
    CreateTaskCommand,
    DeleteDailyPlanCommand,
    DeleteGoalCommand,
    DeleteTaskCommand,
    GetDailyPlanCommand,
    GetGoalCommand,
    GetOrCreateDailyPlanCommand,
    GetTaskCommand,
    LinkTaskToGoalCommand,
    ListDailyPlansCommand,
    ListUserGoalsCommand,
    ListUserTasksCommand,
    MarkTaskAsDoingCommand,
    MarkTaskAsDoneCommand,
    PromoteTaskPriorityCommand,
    RemoveTaskFromDailyPlanCommand,
    UnlinkTaskFromGoalCommand,
    UpdateDailyPlanCommand,
    UpdateGoalCommand,
    UpdateTaskCommand,
)
from apps.tasks.application.exceptions import InvalidTasksInput, TasksApplicationError
from apps.tasks.domain.exceptions import (
    DailyPlanFull,
    DailyPlanNotFound,
    GoalNotFound,
    TaskAlreadyDone,
    TaskAlreadyInPlan,
    TaskNotFound,
    TasksDomainError,
)
from apps.tasks.infrastructure import tasks as tasks_infrastructure
from apps.tasks.infrastructure.tasks import (
    decompose_overwhelming_task_celery,
    evaluate_task_celery,
)
from apps.tasks.interfaces.dependencies import build_tasks_use_cases
from apps.tasks.interfaces.serializers import (
    LLM_STATUS_OK,
    LLM_STATUS_UNAVAILABLE,
    CreateDailyPlanSerializer,
    CreateGoalSerializer,
    CreateTaskSerializer,
    DailyPlanRangeQuerySerializer,
    DailyPlanSerializer,
    DailyPlanTaskSerializer,
    GoalSerializer,
    LlmHealthSerializer,
    LlmQueuedSerializer,
    TaskFilterQuerySerializer,
    TaskReferenceSerializer,
    TaskSerializer,
    UpdateDailyPlanSerializer,
    UpdateGoalSerializer,
    UpdateTaskSerializer,
)
from apps.users.interfaces.permissions import IsNotBanned
from config.serializers import ERROR_RESPONSES
from shared.infrastructure.clock import SystemClock

NOT_FOUND_ERRORS = (
    TaskNotFound,
    GoalNotFound,
    DailyPlanNotFound,
)

CONFLICT_ERRORS = (
    DailyPlanFull,
    TaskAlreadyInPlan,
    TaskAlreadyDone,
)

CONFLICT_RESPONSES: dict[int, Any] = {
    status.HTTP_409_CONFLICT: None,
    **ERROR_RESPONSES,
}


class Conflict(APIException):
    """Report a rejected state transition with HTTP 409.

    A full day or an already completed task is a planning decision, not
    malformed input, so it must not be reported as a 400 a client would try to
    "fix" by editing the payload.
    """

    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state."  # type: ignore[assignment]


def _authenticated_user_id(request: Request) -> UUID:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return user_id


def _translate_tasks_error(exc: Exception) -> APIException:
    """Map a use-case failure to its HTTP meaning."""
    if isinstance(exc, NOT_FOUND_ERRORS):
        return NotFound(str(exc))
    if isinstance(exc, CONFLICT_ERRORS):
        return Conflict(str(exc))
    if isinstance(exc, InvalidTasksInput):
        return ValidationError({"detail": str(exc)})
    return ValidationError({"detail": "The request could not be processed."})


def _sent_or_unset(data: dict[str, Any], name: str) -> Any:
    """Return the sent value, ``None`` when cleared, or ``UNSET`` when absent."""
    if name not in data:
        return UNSET
    return data[name]


class _TasksViewSet(GenericViewSet):
    """Shared authentication, permissions, and error translation."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    def handle_exception(self, exc: Exception) -> Any:
        if isinstance(exc, (TasksApplicationError, TasksDomainError)):
            return super().handle_exception(_translate_tasks_error(exc))
        return super().handle_exception(exc)


class TaskViewSet(_TasksViewSet):
    """Create, inspect, and move owner-scoped tasks."""

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Describe the task payload for schema generation and defaults."""
        return TaskSerializer

    @extend_schema(
        operation_id="tasks_list",
        parameters=[TaskFilterQuerySerializer],
        responses={status.HTTP_200_OK: TaskSerializer(many=True), **ERROR_RESPONSES},
        summary="List my tasks",
    )
    def list(self, request: Request) -> Response:
        query = TaskFilterQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        tasks = build_tasks_use_cases().list_user_tasks.execute(
            ListUserTasksCommand(
                user_id=_authenticated_user_id(request),
                status=filters.get("status"),
                goal_id=filters.get("goal_id"),
            )
        )
        return Response([TaskSerializer(task).data for task in tasks])

    @extend_schema(
        operation_id="tasks_create",
        request=CreateTaskSerializer,
        responses={status.HTTP_201_CREATED: TaskSerializer, **ERROR_RESPONSES},
        summary="Create a task",
    )
    def create(self, request: Request) -> Response:
        serializer = CreateTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = build_tasks_use_cases().create_task.execute(
            CreateTaskCommand(
                user_id=_authenticated_user_id(request),
                name=data["name"],
                description=data.get("description", ""),
                importance=data["importance"],
                estimated_hours=data["estimated_hours"],
                due_date=data.get("due_date"),
                goal_id=data.get("goal_id"),
            )
        )
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="tasks_retrieve",
        responses={status.HTTP_200_OK: TaskSerializer, **ERROR_RESPONSES},
        summary="Read one task",
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        task = build_tasks_use_cases().get_task.execute(
            GetTaskCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(TaskSerializer(task).data)

    @extend_schema(
        operation_id="tasks_partial_update",
        request=UpdateTaskSerializer,
        responses={status.HTTP_200_OK: TaskSerializer, **ERROR_RESPONSES},
        summary="Update one task",
    )
    def partial_update(self, request: Request, pk: UUID) -> Response:
        serializer = UpdateTaskSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = build_tasks_use_cases().update_task.execute(
            UpdateTaskCommand(
                task_id=pk,
                user_id=_authenticated_user_id(request),
                name=data.get("name"),
                description=data.get("description"),
                importance=data.get("importance"),
                estimated_hours=data.get("estimated_hours"),
                due_date=_sent_or_unset(data, "due_date"),
            )
        )
        return Response(TaskSerializer(task).data)

    @extend_schema(
        operation_id="tasks_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
        summary="Delete one task",
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        build_tasks_use_cases().delete_task.execute(
            DeleteTaskCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("post",), url_path="mark-doing")
    @extend_schema(
        operation_id="tasks_mark_doing",
        request=None,
        responses={
            status.HTTP_200_OK: TaskSerializer,
            **CONFLICT_RESPONSES,
        },
        summary="Start a task",
    )
    def mark_doing(self, request: Request, pk: UUID) -> Response:
        task = build_tasks_use_cases().mark_task_as_doing.execute(
            MarkTaskAsDoingCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=("post",), url_path="mark-done")
    @extend_schema(
        operation_id="tasks_mark_done",
        request=None,
        responses={
            status.HTTP_200_OK: TaskSerializer,
            **CONFLICT_RESPONSES,
        },
        summary="Complete a task",
    )
    def mark_done(self, request: Request, pk: UUID) -> Response:
        task = build_tasks_use_cases().mark_task_as_done.execute(
            MarkTaskAsDoneCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=("post",), url_path="promote-priority")
    @extend_schema(
        operation_id="tasks_promote_priority",
        request=None,
        responses={status.HTTP_200_OK: TaskSerializer, **ERROR_RESPONSES},
        summary="Raise the importance of a task",
    )
    def promote_priority(self, request: Request, pk: UUID) -> Response:
        task = build_tasks_use_cases().promote_task_priority.execute(
            PromoteTaskPriorityCommand(
                task_id=pk, user_id=_authenticated_user_id(request)
            )
        )
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=("post",), url_path="evaluate")
    @extend_schema(
        operation_id="tasks_evaluate",
        request=None,
        responses={status.HTTP_202_ACCEPTED: LlmQueuedSerializer, **ERROR_RESPONSES},
        summary="Queue an assistant assessment of this task",
        description=(
            "Queues a background assessment of importance and effort. Answers "
            "202 immediately; the outcome arrives on the task's "
            "`is_checked_by_llm` and `llm_evaluation_failed` flags. A task "
            "belonging to somebody else answers 404. This always re-evaluates, "
            "because asking twice is an explicit request rather than noise."
        ),
    )
    def evaluate(self, request: Request, pk: UUID) -> Response:
        # Ownership is settled before anything is queued. The worker resolves the
        # task from storage by id alone, so skipping this check would let one
        # owner's request trigger work on another owner's task.
        build_tasks_use_cases().get_task.execute(
            GetTaskCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        evaluate_task_celery.delay(str(pk), True)
        return Response(
            {"detail": "Evaluation queued.", "task_id": pk, "queued": True},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=("post",), url_path="decompose")
    @extend_schema(
        operation_id="tasks_decompose",
        request=None,
        responses={status.HTTP_202_ACCEPTED: LlmQueuedSerializer, **ERROR_RESPONSES},
        summary="Queue an assistant decomposition of this task",
        description=(
            "Queues a background decomposition of a task whose estimate is "
            "above the overwhelming threshold. Answers 202 immediately. A task "
            "that is not overwhelming is left untouched by the worker."
        ),
    )
    def decompose(self, request: Request, pk: UUID) -> Response:
        build_tasks_use_cases().get_task.execute(
            GetTaskCommand(task_id=pk, user_id=_authenticated_user_id(request))
        )
        decompose_overwhelming_task_celery.delay(str(pk))
        return Response(
            {"detail": "Decomposition queued.", "task_id": pk, "queued": True},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=("get",), url_path="llm-health")
    @extend_schema(
        operation_id="tasks_llm_health",
        responses={
            status.HTTP_200_OK: LlmHealthSerializer,
            status.HTTP_503_SERVICE_UNAVAILABLE: LlmHealthSerializer,
            **ERROR_RESPONSES,
        },
        summary="Check that the assistant provider is reachable",
        description=(
            "Reports whether the local assistant daemon answers. An unreachable "
            "provider is a 503 rather than a server error, because every "
            "assisted feature degrades to a recorded flag instead of failing."
        ),
    )
    def llm_health(self, request: Request) -> Response:
        del request
        # Reached through the module so the worker and the view share one seam:
        # the client is configured identically in both places.
        client = tasks_infrastructure.build_llm_client()
        availability = client.probe()
        if availability.available:
            return Response(
                {"status": LLM_STATUS_OK, "model": client.settings.model},
                status=status.HTTP_200_OK,
            )
        # No model name when unreachable: the configured name says nothing about
        # what would actually run, and reporting it would imply otherwise.
        return Response(
            {
                "status": LLM_STATUS_UNAVAILABLE,
                "model": None,
                "error": availability.reason,
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class GoalViewSet(_TasksViewSet):
    """Manage owner-scoped goals and their task associations."""

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Describe the goal payload for schema generation and defaults."""
        return GoalSerializer

    @extend_schema(
        operation_id="goals_list",
        responses={status.HTTP_200_OK: GoalSerializer(many=True), **ERROR_RESPONSES},
        summary="List my goals",
    )
    def list(self, request: Request) -> Response:
        goals = build_tasks_use_cases().list_user_goals.execute(
            ListUserGoalsCommand(user_id=_authenticated_user_id(request))
        )
        return Response([GoalSerializer(goal).data for goal in goals])

    @extend_schema(
        operation_id="goals_create",
        request=CreateGoalSerializer,
        responses={status.HTTP_201_CREATED: GoalSerializer, **ERROR_RESPONSES},
        summary="Create a goal",
    )
    def create(self, request: Request) -> Response:
        serializer = CreateGoalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        goal = build_tasks_use_cases().create_goal.execute(
            CreateGoalCommand(
                user_id=_authenticated_user_id(request),
                name=data["name"],
                description=data.get("description", ""),
                due_date=data.get("due_date"),
            )
        )
        return Response(GoalSerializer(goal).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="goals_retrieve",
        responses={status.HTTP_200_OK: GoalSerializer, **ERROR_RESPONSES},
        summary="Read one goal",
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        goal = build_tasks_use_cases().get_goal.execute(
            GetGoalCommand(goal_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(GoalSerializer(goal).data)

    @extend_schema(
        operation_id="goals_partial_update",
        request=UpdateGoalSerializer,
        responses={status.HTTP_200_OK: GoalSerializer, **ERROR_RESPONSES},
        summary="Update one goal",
    )
    def partial_update(self, request: Request, pk: UUID) -> Response:
        serializer = UpdateGoalSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        goal = build_tasks_use_cases().update_goal.execute(
            UpdateGoalCommand(
                goal_id=pk,
                user_id=_authenticated_user_id(request),
                name=data.get("name"),
                description=data.get("description"),
                due_date=_sent_or_unset(data, "due_date"),
            )
        )
        return Response(GoalSerializer(goal).data)

    @extend_schema(
        operation_id="goals_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
        summary="Delete a goal and keep its tasks",
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        build_tasks_use_cases().delete_goal.execute(
            DeleteGoalCommand(goal_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("post",), url_path="link-task")
    @extend_schema(
        operation_id="goals_link_task",
        request=TaskReferenceSerializer,
        responses={status.HTTP_200_OK: TaskSerializer, **ERROR_RESPONSES},
        summary="Attach a task to this goal",
    )
    def link_task(self, request: Request, pk: UUID) -> Response:
        serializer = TaskReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = build_tasks_use_cases().link_task_to_goal.execute(
            LinkTaskToGoalCommand(
                goal_id=pk,
                task_id=serializer.validated_data["task_id"],
                user_id=_authenticated_user_id(request),
            )
        )
        return Response(TaskSerializer(task).data)

    @action(detail=True, methods=("post",), url_path="unlink-task")
    @extend_schema(
        operation_id="goals_unlink_task",
        request=TaskReferenceSerializer,
        responses={status.HTTP_200_OK: TaskSerializer, **ERROR_RESPONSES},
        summary="Detach a task from this goal",
    )
    def unlink_task(self, request: Request, pk: UUID) -> Response:
        serializer = TaskReferenceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = build_tasks_use_cases().unlink_task_from_goal.execute(
            UnlinkTaskFromGoalCommand(
                goal_id=pk,
                task_id=serializer.validated_data["task_id"],
                user_id=_authenticated_user_id(request),
            )
        )
        return Response(TaskSerializer(task).data)


class DailyPlanViewSet(_TasksViewSet):
    """Plan and inspect the tasks scheduled for a day."""

    def get_serializer_class(self) -> type[serializers.Serializer]:
        """Describe the daily plan payload for schema generation and defaults."""
        return DailyPlanSerializer

    @extend_schema(
        operation_id="daily_plans_list",
        parameters=[DailyPlanRangeQuerySerializer],
        responses={
            status.HTTP_200_OK: DailyPlanSerializer(many=True),
            **ERROR_RESPONSES,
        },
        summary="List my daily plans",
    )
    def list(self, request: Request) -> Response:
        query = DailyPlanRangeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        filters = query.validated_data
        start_date = filters.get("start_date")
        end_date = filters.get("end_date")
        if start_date is None and end_date is None:
            # A bare list answers with the plan of today, which is what a user
            # opening the app wants; the range is only needed for history.
            start_date = SystemClock().today()
            end_date = start_date
        plans = build_tasks_use_cases().list_daily_plans.execute(
            ListDailyPlansCommand(
                user_id=_authenticated_user_id(request),
                start_date=start_date if start_date else end_date,
                end_date=end_date if end_date else start_date,
            )
        )
        return Response([DailyPlanSerializer(plan).data for plan in plans])

    @extend_schema(
        operation_id="daily_plans_create",
        request=CreateDailyPlanSerializer,
        responses={status.HTTP_201_CREATED: DailyPlanSerializer, **ERROR_RESPONSES},
        summary="Open the plan of one day",
    )
    def create(self, request: Request) -> Response:
        serializer = CreateDailyPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = build_tasks_use_cases().get_or_create_daily_plan.execute(
            GetOrCreateDailyPlanCommand(
                user_id=_authenticated_user_id(request),
                date=serializer.validated_data["date"],
            )
        )
        return Response(DailyPlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        operation_id="daily_plans_retrieve",
        responses={status.HTTP_200_OK: DailyPlanSerializer, **ERROR_RESPONSES},
        summary="Read one daily plan",
    )
    def retrieve(self, request: Request, pk: UUID) -> Response:
        plan = build_tasks_use_cases().get_daily_plan.execute(
            GetDailyPlanCommand(plan_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(DailyPlanSerializer(plan).data)

    @extend_schema(
        operation_id="daily_plans_partial_update",
        request=UpdateDailyPlanSerializer,
        responses={status.HTTP_200_OK: DailyPlanSerializer, **ERROR_RESPONSES},
        summary="Record how one daily plan was built",
    )
    def partial_update(self, request: Request, pk: UUID) -> Response:
        serializer = UpdateDailyPlanSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        plan = build_tasks_use_cases().update_daily_plan.execute(
            UpdateDailyPlanCommand(
                plan_id=pk,
                user_id=_authenticated_user_id(request),
                generated_by_llm=_sent_or_unset(
                    serializer.validated_data, "generated_by_llm"
                ),
            )
        )
        return Response(DailyPlanSerializer(plan).data)

    @extend_schema(
        operation_id="daily_plans_destroy",
        responses={status.HTTP_204_NO_CONTENT: None, **ERROR_RESPONSES},
        summary="Discard one daily plan",
    )
    def destroy(self, request: Request, pk: UUID) -> Response:
        build_tasks_use_cases().delete_daily_plan.execute(
            DeleteDailyPlanCommand(plan_id=pk, user_id=_authenticated_user_id(request))
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("post",), url_path="add-task")
    @extend_schema(
        operation_id="daily_plans_add_task",
        request=DailyPlanTaskSerializer,
        responses={
            status.HTTP_200_OK: DailyPlanSerializer,
            **CONFLICT_RESPONSES,
        },
        summary="Schedule a task on this day",
    )
    def add_task(self, request: Request, pk: UUID) -> Response:
        serializer = DailyPlanTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = build_tasks_use_cases().add_task_to_daily_plan.execute(
            AddTaskToDailyPlanCommand(
                plan_id=pk,
                task_id=serializer.validated_data["task_id"],
                user_id=_authenticated_user_id(request),
            )
        )
        return Response(DailyPlanSerializer(plan).data)

    @action(detail=True, methods=("post",), url_path="remove-task")
    @extend_schema(
        operation_id="daily_plans_remove_task",
        request=DailyPlanTaskSerializer,
        responses={
            status.HTTP_200_OK: DailyPlanSerializer,
            **CONFLICT_RESPONSES,
        },
        summary="Unschedule a task from this day",
    )
    def remove_task(self, request: Request, pk: UUID) -> Response:
        serializer = DailyPlanTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = build_tasks_use_cases().remove_task_from_daily_plan.execute(
            RemoveTaskFromDailyPlanCommand(
                plan_id=pk,
                task_id=serializer.validated_data["task_id"],
                user_id=_authenticated_user_id(request),
            )
        )
        return Response(DailyPlanSerializer(plan).data)
