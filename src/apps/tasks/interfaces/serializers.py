"""DRF input and output serializers for the tasks context.

Requests are validated here and nowhere else: these serializers translate a
payload into the primitives a command expects. Missing fields stay missing, so
the ``UNSET`` sentinel reaches the use case and the stored value survives; an
explicit ``null`` becomes ``None`` and clears the column.
"""

from rest_framework import serializers

from apps.tasks.domain.value_objects import (
    GOAL_STATUS_CHOICES,
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    PRIORITY_CHOICES,
    TASK_STATUS_CHOICES,
)

HOURS_FIELD_KWARGS = {
    "max_digits": 12,
    "decimal_places": 2,
    "min_value": 0,
}

LLM_STATUS_OK = "ok"
LLM_STATUS_UNAVAILABLE = "unavailable"

LLM_STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    (LLM_STATUS_OK, "Ok"),
    (LLM_STATUS_UNAVAILABLE, "Unavailable"),
)


class CreateTaskSerializer(serializers.Serializer):
    """Validate the fields required to create a task."""

    name = serializers.CharField(max_length=MAX_NAME_LENGTH, allow_blank=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        default="",
    )
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    importance = serializers.ChoiceField(
        choices=PRIORITY_CHOICES,
        required=False,
        default="medium",
    )
    estimated_hours = serializers.DecimalField(**HOURS_FIELD_KWARGS)
    goal_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class UpdateTaskSerializer(serializers.Serializer):
    """Validate a partial task update.

    Nothing is required, and absent keys are simply absent from
    ``validated_data``; the view turns those into ``UNSET``.
    """

    name = serializers.CharField(
        max_length=MAX_NAME_LENGTH,
        allow_blank=False,
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    due_date = serializers.DateField(required=False, allow_null=True)
    importance = serializers.ChoiceField(choices=PRIORITY_CHOICES, required=False)
    estimated_hours = serializers.DecimalField(required=False, **HOURS_FIELD_KWARGS)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide name, description, due_date, importance, or estimated_hours."
            )
        return attrs


class TaskSerializer(serializers.Serializer):
    """Represent a safe task application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    goal_id = serializers.UUIDField(
        source="goal_id.value", read_only=True, allow_null=True
    )
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    due_date = serializers.DateField(read_only=True, allow_null=True)
    importance = serializers.ChoiceField(choices=PRIORITY_CHOICES, read_only=True)
    estimated_hours = serializers.DecimalField(read_only=True, **HOURS_FIELD_KWARGS)
    status = serializers.ChoiceField(choices=TASK_STATUS_CHOICES, read_only=True)
    is_overwhelmed = serializers.BooleanField(read_only=True)
    is_checked_by_llm = serializers.BooleanField(read_only=True)
    llm_evaluation_failed = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class TaskReferenceSerializer(serializers.Serializer):
    """Accept the task a goal action operates on."""

    task_id = serializers.UUIDField()


class CreateGoalSerializer(serializers.Serializer):
    """Validate the fields required to create a goal."""

    name = serializers.CharField(max_length=MAX_NAME_LENGTH, allow_blank=False)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
        default="",
    )
    due_date = serializers.DateField(required=False, allow_null=True, default=None)


class UpdateGoalSerializer(serializers.Serializer):
    """Validate a partial goal update."""

    name = serializers.CharField(
        max_length=MAX_NAME_LENGTH,
        allow_blank=False,
        required=False,
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=MAX_DESCRIPTION_LENGTH,
    )
    due_date = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide name, description, or due_date.")
        return attrs


class GoalSerializer(serializers.Serializer):
    """Represent a safe goal application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True, allow_blank=True)
    due_date = serializers.DateField(read_only=True, allow_null=True)
    status = serializers.ChoiceField(choices=GOAL_STATUS_CHOICES, read_only=True)
    task_count = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class CreateDailyPlanSerializer(serializers.Serializer):
    """Validate the fields required to create a daily plan."""

    date = serializers.DateField()


class UpdateDailyPlanSerializer(serializers.Serializer):
    """Validate a partial daily plan update.

    Scheduling is exposed through the ``add-task``/``remove-task`` actions, so
    only the LLM provenance flag is editable here.
    """

    generated_by_llm = serializers.BooleanField(required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide generated_by_llm.")
        return attrs


class DailyPlanSerializer(serializers.Serializer):
    """Represent a safe daily plan application result."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    date = serializers.DateField(read_only=True)
    tasks = TaskSerializer(many=True, read_only=True)
    total_hours = serializers.DecimalField(read_only=True, **HOURS_FIELD_KWARGS)
    is_full = serializers.BooleanField(read_only=True)
    generated_by_llm = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class DailyPlanTaskSerializer(serializers.Serializer):
    """Accept the task scheduled on or removed from a day."""

    task_id = serializers.UUIDField()


class DailyPlanRangeQuerySerializer(serializers.Serializer):
    """Validate the query parameters of the daily plan list endpoint."""

    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)


class TaskFilterQuerySerializer(serializers.Serializer):
    """Validate the query parameters of the task list endpoint."""

    status = serializers.ChoiceField(choices=TASK_STATUS_CHOICES, required=False)
    goal_id = serializers.UUIDField(required=False)


class LlmQueuedSerializer(serializers.Serializer):
    """Report that assistant work was accepted for background processing.

    The response deliberately describes the *request*, not the result: the work
    happens after this response is written, so claiming an outcome here would be
    a guess.
    """

    detail = serializers.CharField(read_only=True)
    task_id = serializers.UUIDField(read_only=True)
    queued = serializers.BooleanField(read_only=True)


class LlmHealthSerializer(serializers.Serializer):
    """Report whether the assistant provider is reachable."""

    status = serializers.ChoiceField(choices=LLM_STATUS_CHOICES, read_only=True)
    model = serializers.CharField(read_only=True, allow_null=True, required=False)
    error = serializers.CharField(read_only=True, allow_null=True, required=False)
