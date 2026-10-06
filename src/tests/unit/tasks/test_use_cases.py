"""Tasks use-case tests: owner scoping, validation, and planning outcomes."""

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.tasks.application.commands import (
    AddTaskToDailyPlanCommand,
    CreateGoalCommand,
    CreateTaskCommand,
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
    UpdateGoalCommand,
    UpdateTaskCommand,
)
from apps.tasks.application.config import (
    PLANNING_POLICY,
    TASKS_DEFAULTS,
    PlanningPolicy,
)
from apps.tasks.application.dto import GoalDetails, TaskDetails, ordered_tasks
from apps.tasks.application.exceptions import InvalidTasksInput
from apps.tasks.application.use_cases.daily_plans import (
    AddTaskToDailyPlan,
    GetDailyPlan,
    GetOrCreateDailyPlan,
    ListDailyPlans,
    RemoveTaskFromDailyPlan,
)
from apps.tasks.application.use_cases.goals import (
    CreateGoal,
    DeleteGoal,
    GetGoal,
    LinkTaskToGoal,
    ListUserGoals,
    UnlinkTaskFromGoal,
    UpdateGoal,
)
from apps.tasks.application.use_cases.tasks import (
    CreateTask,
    DeleteTask,
    GetTask,
    ListUserTasks,
    MarkTaskAsDoing,
    MarkTaskAsDone,
    PromoteTaskPriority,
    UpdateTask,
)
from apps.tasks.domain.exceptions import (
    DailyPlanFull,
    DailyPlanNotFound,
    GoalNotFound,
    TaskAlreadyDone,
    TaskNotFound,
)
from apps.tasks.domain.value_objects import (
    Duration,
    OverwhelmedThreshold,
    Priority,
    TaskStatus,
)
from tests.unit.tasks.fakes import (
    FakeClock,
    FakeDailyPlanRepository,
    FakeGoalRepository,
    FakeTaskRepository,
)

pytestmark = pytest.mark.unit

OWNER = uuid4()
STRANGER = uuid4()
SMALL_POLICY = PlanningPolicy(
    overwhelmed_threshold=OverwhelmedThreshold(Decimal("1.0")),
    daily_plan_max_hours=Duration(Decimal("2.00")),
)


@pytest.fixture
def tasks() -> FakeTaskRepository:
    return FakeTaskRepository()


@pytest.fixture
def goals() -> FakeGoalRepository:
    return FakeGoalRepository()


@pytest.fixture
def plans() -> FakeDailyPlanRepository:
    return FakeDailyPlanRepository()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def _create_task(
    tasks: FakeTaskRepository,
    *,
    user_id: UUID = OWNER,
    name: str = "Water the plants",
    hours: str = "1.00",
    importance: str = "medium",
    due_date: date | None = None,
) -> TaskDetails:
    return CreateTask(tasks, FakeClock()).execute(
        CreateTaskCommand(
            user_id=user_id,
            name=name,
            description="",
            importance=importance,
            estimated_hours=Decimal(hours),
            due_date=due_date,
        )
    )


def _create_goal(goals: FakeGoalRepository, *, user_id: UUID = OWNER) -> GoalDetails:
    return CreateGoal(goals, FakeClock()).execute(
        CreateGoalCommand(
            user_id=user_id,
            name="Spring cleaning",
            description="",
        )
    )


# --- configuration ---------------------------------------------------------


def test_config_exposes_product_defaults() -> None:
    assert TASKS_DEFAULTS["OVERWHELMED_THRESHOLD_HOURS"] == Decimal("4.0")
    assert TASKS_DEFAULTS["DAILY_PLAN_MAX_HOURS"] == Decimal("8.0")
    assert PLANNING_POLICY.overwhelmed_threshold.hours == Decimal("4.0")
    assert PLANNING_POLICY.daily_plan_max_hours.hours == Decimal("8.0")


# --- task use cases --------------------------------------------------------


def test_create_task_persists_and_maps_details(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks, due_date=date(2026, 2, 1))

    assert details.name == "Water the plants"
    assert details.status is TaskStatus.TODO
    assert details.estimated_hours == Decimal("1.00")
    assert details.is_overwhelmed is False
    assert details.due_date == date(2026, 2, 1)
    assert len(tasks.tasks) == 1


def test_create_task_computes_is_overwhelmed_with_injected_policy(
    tasks: FakeTaskRepository,
) -> None:
    details = CreateTask(tasks, FakeClock(), SMALL_POLICY).execute(
        CreateTaskCommand(
            user_id=OWNER,
            name="Big job",
            description="",
            importance="high",
            estimated_hours=Decimal("5.00"),
        )
    )

    assert details.is_overwhelmed is True


def test_create_task_rejects_invalid_input(tasks: FakeTaskRepository) -> None:
    with pytest.raises(InvalidTasksInput):
        CreateTask(tasks, FakeClock()).execute(
            CreateTaskCommand(
                user_id=OWNER,
                name="  ",
                description="",
                importance="medium",
                estimated_hours=Decimal("1.00"),
            )
        )
    with pytest.raises(InvalidTasksInput):
        CreateTask(tasks, FakeClock()).execute(
            CreateTaskCommand(
                user_id=OWNER,
                name="Valid",
                description="",
                importance="urgent",
                estimated_hours=Decimal("1.00"),
            )
        )
    with pytest.raises(InvalidTasksInput):
        CreateTask(tasks, FakeClock()).execute(
            CreateTaskCommand(
                user_id=OWNER,
                name="Valid",
                description="",
                importance="medium",
                estimated_hours=Decimal("-1.00"),
            )
        )
    assert tasks.tasks == {}


def test_get_task_hides_foreign_and_missing_tasks(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks)

    assert (
        GetTask(tasks)
        .execute(GetTaskCommand(task_id=details.id.value, user_id=OWNER))
        .id
        == details.id
    )
    with pytest.raises(TaskNotFound):
        GetTask(tasks).execute(
            GetTaskCommand(task_id=details.id.value, user_id=STRANGER)
        )
    with pytest.raises(TaskNotFound):
        GetTask(tasks).execute(GetTaskCommand(task_id=uuid4(), user_id=OWNER))


def test_list_user_tasks_filters_by_status_and_goal(
    tasks: FakeTaskRepository, goals: FakeGoalRepository
) -> None:
    goal_id = _create_goal(goals).id.value
    first = _create_task(tasks, name="First")
    second = _create_task(tasks, name="Second")
    _create_task(tasks, name="Someone else's", user_id=STRANGER)

    LinkTaskToGoal(tasks, goals, FakeClock()).execute(
        LinkTaskToGoalCommand(goal_id=goal_id, task_id=second.id.value, user_id=OWNER)
    )
    MarkTaskAsDone(tasks, FakeClock()).execute(
        MarkTaskAsDoneCommand(task_id=first.id.value, user_id=OWNER)
    )

    listed = ListUserTasks(tasks).execute(ListUserTasksCommand(user_id=OWNER))
    assert [item.name for item in listed] == ["First", "Second"]

    by_status = ListUserTasks(tasks).execute(
        ListUserTasksCommand(user_id=OWNER, status="done")
    )
    assert [item.name for item in by_status] == ["First"]

    by_goal = ListUserTasks(tasks).execute(
        ListUserTasksCommand(user_id=OWNER, goal_id=goal_id)
    )
    assert [item.name for item in by_goal] == ["Second"]

    with pytest.raises(InvalidTasksInput):
        ListUserTasks(tasks).execute(
            ListUserTasksCommand(user_id=OWNER, status="archived")
        )


def test_update_task_applies_partial_changes_and_resets_llm_flag(
    tasks: FakeTaskRepository,
) -> None:
    details = _create_task(tasks, due_date=date(2026, 2, 1))

    updated = UpdateTask(tasks, FakeClock()).execute(
        UpdateTaskCommand(
            task_id=details.id.value,
            user_id=OWNER,
            importance="high",
            estimated_hours=Decimal("2.50"),
        )
    )

    assert updated.name == "Water the plants"
    assert updated.importance is Priority.HIGH
    assert updated.estimated_hours == Decimal("2.50")
    assert updated.due_date == date(2026, 2, 1)
    assert updated.is_checked_by_llm is False


def test_update_task_can_clear_the_due_date(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks, due_date=date(2026, 2, 1))

    cleared = UpdateTask(tasks, FakeClock()).execute(
        UpdateTaskCommand(task_id=details.id.value, user_id=OWNER, due_date=None)
    )
    assert cleared.due_date is None

    kept = UpdateTask(tasks, FakeClock()).execute(
        UpdateTaskCommand(task_id=details.id.value, user_id=OWNER, name="Renamed")
    )
    assert kept.due_date is None

    reset = UpdateTask(tasks, FakeClock()).execute(
        UpdateTaskCommand(
            task_id=details.id.value,
            user_id=OWNER,
            due_date=date(2026, 3, 1),
        )
    )
    assert reset.due_date == date(2026, 3, 1)


def test_update_task_requires_at_least_one_field(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks)

    with pytest.raises(InvalidTasksInput):
        UpdateTask(tasks, FakeClock()).execute(
            UpdateTaskCommand(task_id=details.id.value, user_id=OWNER)
        )
    with pytest.raises(TaskNotFound):
        UpdateTask(tasks, FakeClock()).execute(
            UpdateTaskCommand(task_id=details.id.value, user_id=STRANGER, name="x")
        )


def test_update_task_translates_domain_validation(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks)

    with pytest.raises(InvalidTasksInput):
        UpdateTask(tasks, FakeClock()).execute(
            UpdateTaskCommand(
                task_id=details.id.value,
                user_id=OWNER,
                estimated_hours=Decimal("-1.00"),
            )
        )


def test_delete_task_is_owner_scoped(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks)

    with pytest.raises(TaskNotFound):
        DeleteTask(tasks).execute(
            DeleteTaskCommand(task_id=details.id.value, user_id=STRANGER)
        )
    assert len(tasks.tasks) == 1

    DeleteTask(tasks).execute(
        DeleteTaskCommand(task_id=details.id.value, user_id=OWNER)
    )
    assert tasks.tasks == {}


def test_task_status_and_priority_transitions(tasks: FakeTaskRepository) -> None:
    details = _create_task(tasks, importance="low")

    doing = MarkTaskAsDoing(tasks, FakeClock()).execute(
        MarkTaskAsDoingCommand(task_id=details.id.value, user_id=OWNER)
    )
    assert doing.status is TaskStatus.DOING

    promoted = PromoteTaskPriority(tasks, FakeClock()).execute(
        PromoteTaskPriorityCommand(task_id=details.id.value, user_id=OWNER)
    )
    assert promoted.importance is Priority.MEDIUM

    done = MarkTaskAsDone(tasks, FakeClock()).execute(
        MarkTaskAsDoneCommand(task_id=details.id.value, user_id=OWNER)
    )
    assert done.status is TaskStatus.DONE

    with pytest.raises(TaskAlreadyDone):
        MarkTaskAsDone(tasks, FakeClock()).execute(
            MarkTaskAsDoneCommand(task_id=details.id.value, user_id=OWNER)
        )
    with pytest.raises(TaskAlreadyDone):
        MarkTaskAsDoing(tasks, FakeClock()).execute(
            MarkTaskAsDoingCommand(task_id=details.id.value, user_id=OWNER)
        )


# --- goal use cases --------------------------------------------------------


def test_create_and_get_goal_with_task_count(
    tasks: FakeTaskRepository, goals: FakeGoalRepository
) -> None:
    goal = _create_goal(goals)
    _create_task(tasks)

    assert goal.task_count == 0
    assert (
        GetGoal(goals, tasks)
        .execute(GetGoalCommand(goal_id=goal.id.value, user_id=OWNER))
        .task_count
        == 0
    )


def test_get_goal_hides_foreign_goals(goals: FakeGoalRepository) -> None:
    goal = _create_goal(goals)

    with pytest.raises(GoalNotFound):
        GetGoal(goals, FakeTaskRepository()).execute(
            GetGoalCommand(goal_id=goal.id.value, user_id=STRANGER)
        )


def test_list_user_goals_counts_tasks_only_for_owner(
    tasks: FakeTaskRepository, goals: FakeGoalRepository
) -> None:
    goal = _create_goal(goals)
    _create_goal(goals, user_id=STRANGER)
    task = _create_task(tasks)
    LinkTaskToGoal(tasks, goals, FakeClock()).execute(
        LinkTaskToGoalCommand(
            goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
        )
    )

    listed = ListUserGoals(goals, tasks).execute(ListUserGoalsCommand(user_id=OWNER))

    assert [item.name for item in listed] == ["Spring cleaning"]
    assert listed[0].task_count == 1


def test_update_goal_applies_partial_changes(goals: FakeGoalRepository) -> None:
    goal = _create_goal(goals)

    renamed = UpdateGoal(goals, FakeTaskRepository(), FakeClock()).execute(
        UpdateGoalCommand(
            goal_id=goal.id.value, user_id=OWNER, name="  Deep cleaning  "
        )
    )
    assert renamed.name == "Deep cleaning"

    with pytest.raises(InvalidTasksInput):
        UpdateGoal(goals, FakeTaskRepository(), FakeClock()).execute(
            UpdateGoalCommand(goal_id=goal.id.value, user_id=OWNER)
        )


def test_link_and_unlink_task_to_goal(
    tasks: FakeTaskRepository, goals: FakeGoalRepository
) -> None:
    goal = _create_goal(goals)
    task = _create_task(tasks)

    linked = LinkTaskToGoal(tasks, goals, FakeClock()).execute(
        LinkTaskToGoalCommand(
            goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
        )
    )
    assert linked.goal_id == goal.id

    with pytest.raises(InvalidTasksInput):
        LinkTaskToGoal(tasks, goals, FakeClock()).execute(
            LinkTaskToGoalCommand(
                goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
            )
        )
    with pytest.raises(GoalNotFound):
        LinkTaskToGoal(tasks, goals, FakeClock()).execute(
            LinkTaskToGoalCommand(goal_id=uuid4(), task_id=task.id.value, user_id=OWNER)
        )

    unlinked = UnlinkTaskFromGoal(tasks, goals, FakeClock()).execute(
        UnlinkTaskFromGoalCommand(
            goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
        )
    )
    assert unlinked.goal_id is None

    with pytest.raises(InvalidTasksInput):
        UnlinkTaskFromGoal(tasks, goals, FakeClock()).execute(
            UnlinkTaskFromGoalCommand(
                goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
            )
        )


def test_delete_goal_keeps_tasks_but_detaches_them(
    tasks: FakeTaskRepository, goals: FakeGoalRepository
) -> None:
    goal = _create_goal(goals)
    task = _create_task(tasks)
    LinkTaskToGoal(tasks, goals, FakeClock()).execute(
        LinkTaskToGoalCommand(
            goal_id=goal.id.value, task_id=task.id.value, user_id=OWNER
        )
    )

    with pytest.raises(GoalNotFound):
        DeleteGoal(goals, tasks, FakeClock()).execute(
            DeleteGoalCommand(goal_id=goal.id.value, user_id=STRANGER)
        )
    assert len(goals.goals) == 1

    DeleteGoal(goals, tasks, FakeClock()).execute(
        DeleteGoalCommand(goal_id=goal.id.value, user_id=OWNER)
    )

    assert goals.goals == {}
    assert len(tasks.tasks) == 1
    assert (
        GetTask(tasks)
        .execute(GetTaskCommand(task_id=task.id.value, user_id=OWNER))
        .goal_id
        is None
    )


# --- daily plan use cases --------------------------------------------------


def test_get_or_create_daily_plan_creates_once(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    first = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )
    second = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )

    assert first.id == second.id
    assert first.total_hours == Decimal("0")
    assert first.is_full is False
    assert first.generated_by_llm is False
    assert len(plans.plans) == 1


def test_get_or_create_daily_plan_rejects_invalid_date(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    with pytest.raises(InvalidTasksInput):
        GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
            GetOrCreateDailyPlanCommand(user_id=OWNER, date=FakeClock().now())
        )
    assert plans.plans == {}


def test_add_and_remove_task_from_daily_plan(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    plan = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )
    task = _create_task(tasks, hours="2.00")

    filled = AddTaskToDailyPlan(plans, tasks).execute(
        AddTaskToDailyPlanCommand(
            plan_id=plan.id.value, task_id=task.id.value, user_id=OWNER
        )
    )
    assert filled.total_hours == Decimal("2.00")
    assert [item.name for item in filled.tasks] == ["Water the plants"]
    assert filled.is_full is False

    emptied = RemoveTaskFromDailyPlan(plans, tasks).execute(
        RemoveTaskFromDailyPlanCommand(
            plan_id=plan.id.value, task_id=task.id.value, user_id=OWNER
        )
    )
    assert emptied.total_hours == Decimal("0")
    assert emptied.tasks == ()

    with pytest.raises(DailyPlanNotFound):
        RemoveTaskFromDailyPlan(plans, tasks).execute(
            RemoveTaskFromDailyPlanCommand(
                plan_id=plan.id.value, task_id=task.id.value, user_id=OWNER
            )
        )


def test_add_task_to_daily_plan_refuses_to_exceed_budget(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    plan = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )
    first = _create_task(tasks, name="First", hours="1.50")
    second = _create_task(tasks, name="Second", hours="1.00")
    third = _create_task(tasks, name="Third", hours="0.25")

    filling = AddTaskToDailyPlan(plans, tasks, SMALL_POLICY).execute(
        AddTaskToDailyPlanCommand(
            plan_id=plan.id.value, task_id=first.id.value, user_id=OWNER
        )
    )
    assert filling.total_hours == Decimal("1.50")
    assert filling.is_full is False

    reached = AddTaskToDailyPlan(plans, tasks, SMALL_POLICY).execute(
        AddTaskToDailyPlanCommand(
            plan_id=plan.id.value, task_id=second.id.value, user_id=OWNER
        )
    )
    assert reached.total_hours == Decimal("2.50")
    assert reached.is_full is True

    # Once the budget is reached the day stops accepting work.
    with pytest.raises(DailyPlanFull):
        AddTaskToDailyPlan(plans, tasks, SMALL_POLICY).execute(
            AddTaskToDailyPlanCommand(
                plan_id=plan.id.value, task_id=third.id.value, user_id=OWNER
            )
        )
    assert len(plans.get_by_id(plan.id).task_ids) == 2  # type: ignore[union-attr]


def test_daily_plan_operations_are_owner_scoped(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    plan = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )
    foreign_task = _create_task(tasks, user_id=STRANGER)

    with pytest.raises(DailyPlanNotFound):
        GetDailyPlan(plans, tasks).execute(
            GetDailyPlanCommand(plan_id=plan.id.value, user_id=STRANGER)
        )
    with pytest.raises(DailyPlanNotFound):
        AddTaskToDailyPlan(plans, tasks).execute(
            AddTaskToDailyPlanCommand(
                plan_id=uuid4(), task_id=foreign_task.id.value, user_id=OWNER
            )
        )
    with pytest.raises(TaskNotFound):
        AddTaskToDailyPlan(plans, tasks).execute(
            AddTaskToDailyPlanCommand(
                plan_id=plan.id.value, task_id=foreign_task.id.value, user_id=OWNER
            )
        )
    assert len(plans.get_by_id(plan.id).task_ids) == 0  # type: ignore[union-attr]


def test_daily_plan_details_follow_plan_order(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    plan = GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=OWNER, date=date(2026, 1, 15))
    )
    first = _create_task(tasks, name="First")
    second = _create_task(tasks, name="Second")

    AddTaskToDailyPlan(plans, tasks).execute(
        AddTaskToDailyPlanCommand(
            plan_id=plan.id.value, task_id=first.id.value, user_id=OWNER
        )
    )
    AddTaskToDailyPlan(plans, tasks).execute(
        AddTaskToDailyPlanCommand(
            plan_id=plan.id.value, task_id=second.id.value, user_id=OWNER
        )
    )

    stored = plans.get_by_id(plan.id)
    assert stored is not None
    shuffled = [tasks.tasks[second.id], tasks.tasks[first.id]]
    assert [task.name for task in ordered_tasks(stored, shuffled)] == [
        "First",
        "Second",
    ]


def test_list_daily_plans_validates_and_scopes_the_range(
    tasks: FakeTaskRepository, plans: FakeDailyPlanRepository
) -> None:
    for day in (date(2026, 1, 14), date(2026, 1, 15), date(2026, 1, 20)):
        GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
            GetOrCreateDailyPlanCommand(user_id=OWNER, date=day)
        )
    GetOrCreateDailyPlan(plans, tasks, FakeClock()).execute(
        GetOrCreateDailyPlanCommand(user_id=STRANGER, date=date(2026, 1, 15))
    )

    listed = ListDailyPlans(plans, tasks).execute(
        ListDailyPlansCommand(
            user_id=OWNER,
            start_date=date(2026, 1, 14),
            end_date=date(2026, 1, 15),
        )
    )
    assert [item.date for item in listed] == [date(2026, 1, 14), date(2026, 1, 15)]

    with pytest.raises(InvalidTasksInput):
        ListDailyPlans(plans, tasks).execute(
            ListDailyPlansCommand(
                user_id=OWNER,
                start_date=date(2026, 1, 15),
                end_date=date(2026, 1, 14),
            )
        )
