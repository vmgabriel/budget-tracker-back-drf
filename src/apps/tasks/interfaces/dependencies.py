"""Composition root for the tasks bounded context."""

from dataclasses import dataclass

from apps.tasks.application.config import PLANNING_POLICY, PlanningPolicy
from apps.tasks.application.ports.llm import LlmAssistant
from apps.tasks.application.use_cases import (
    AddTaskToDailyPlan,
    CreateGoal,
    CreateTask,
    DecomposeOverwhelmingTask,
    DeleteDailyPlan,
    DeleteGoal,
    DeleteTask,
    EvaluateTaskWithLlm,
    GenerateDailyPlanWithLlm,
    GetDailyPlan,
    GetGoal,
    GetOrCreateDailyPlan,
    GetTask,
    LinkTaskToGoal,
    ListDailyPlans,
    ListUserGoals,
    ListUserTasks,
    MarkTaskAsDoing,
    MarkTaskAsDone,
    PromoteTaskPriority,
    RemoveTaskFromDailyPlan,
    UnlinkTaskFromGoal,
    UpdateDailyPlan,
    UpdateGoal,
    UpdateTask,
)
from apps.tasks.infrastructure.persistence.repositories import (
    DjangoDailyPlanRepository,
    DjangoGoalRepository,
    DjangoTaskRepository,
)
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class TasksUseCases:
    """Tasks use cases sharing one set of persistence adapters.

    The three assistant-backed use cases are optional: ``assistant=None`` is the
    normal request-scoped configuration, because assistance is queued for a
    worker and never performed inside an HTTP request. Callers that need them
    (Celery tasks) inject a real client.
    """

    policy: PlanningPolicy
    create_task: CreateTask
    get_task: GetTask
    list_user_tasks: ListUserTasks
    update_task: UpdateTask
    delete_task: DeleteTask
    mark_task_as_doing: MarkTaskAsDoing
    mark_task_as_done: MarkTaskAsDone
    promote_task_priority: PromoteTaskPriority
    create_goal: CreateGoal
    get_goal: GetGoal
    list_user_goals: ListUserGoals
    update_goal: UpdateGoal
    delete_goal: DeleteGoal
    link_task_to_goal: LinkTaskToGoal
    unlink_task_from_goal: UnlinkTaskFromGoal
    get_or_create_daily_plan: GetOrCreateDailyPlan
    get_daily_plan: GetDailyPlan
    update_daily_plan: UpdateDailyPlan
    delete_daily_plan: DeleteDailyPlan
    add_task_to_daily_plan: AddTaskToDailyPlan
    remove_task_from_daily_plan: RemoveTaskFromDailyPlan
    list_daily_plans: ListDailyPlans
    evaluate_task_with_llm: EvaluateTaskWithLlm | None = None
    decompose_overwhelming_task: DecomposeOverwhelmingTask | None = None
    generate_daily_plan_with_llm: GenerateDailyPlanWithLlm | None = None


def build_tasks_use_cases(
    policy: PlanningPolicy = PLANNING_POLICY,
    assistant: LlmAssistant | None = None,
) -> TasksUseCases:
    """Build tasks use cases with infrastructure dependencies.

    ``policy`` carries the hour budgets. Phase 2 will resolve it per request
    from the caller's profile instead of using the product defaults.

    ``assistant`` stays ``None`` for HTTP requests: no view may call the model.
    The assistant-backed use cases exist only when a client is supplied, and the
    composition root leaves them ``None`` otherwise rather than wiring one that
    would tempt a view into using it. Celery tasks build their own.
    """
    tasks = DjangoTaskRepository()
    goals = DjangoGoalRepository()
    plans = DjangoDailyPlanRepository()
    clock = SystemClock()
    return TasksUseCases(
        policy=policy,
        create_task=CreateTask(tasks, clock, policy),
        get_task=GetTask(tasks, policy),
        list_user_tasks=ListUserTasks(tasks, policy),
        update_task=UpdateTask(tasks, clock, policy),
        delete_task=DeleteTask(tasks),
        mark_task_as_doing=MarkTaskAsDoing(tasks, clock, policy),
        mark_task_as_done=MarkTaskAsDone(tasks, clock, policy),
        promote_task_priority=PromoteTaskPriority(tasks, clock, policy),
        create_goal=CreateGoal(goals, clock),
        get_goal=GetGoal(goals, tasks),
        list_user_goals=ListUserGoals(goals, tasks),
        update_goal=UpdateGoal(goals, tasks, clock),
        delete_goal=DeleteGoal(goals, tasks, clock),
        link_task_to_goal=LinkTaskToGoal(tasks, goals, clock, policy),
        unlink_task_from_goal=UnlinkTaskFromGoal(tasks, goals, clock, policy),
        get_or_create_daily_plan=GetOrCreateDailyPlan(plans, tasks, clock, policy),
        get_daily_plan=GetDailyPlan(plans, tasks, policy),
        update_daily_plan=UpdateDailyPlan(plans, tasks, policy),
        delete_daily_plan=DeleteDailyPlan(plans),
        add_task_to_daily_plan=AddTaskToDailyPlan(plans, tasks, policy),
        remove_task_from_daily_plan=RemoveTaskFromDailyPlan(plans, tasks, policy),
        list_daily_plans=ListDailyPlans(plans, tasks, policy),
        evaluate_task_with_llm=(
            None
            if assistant is None
            else EvaluateTaskWithLlm(tasks, assistant, clock, policy)
        ),
        decompose_overwhelming_task=(
            None
            if assistant is None
            else DecomposeOverwhelmingTask(tasks, goals, assistant, clock, policy)
        ),
        generate_daily_plan_with_llm=(
            None
            if assistant is None
            else GenerateDailyPlanWithLlm(plans, tasks, assistant, clock, policy)
        ),
    )
