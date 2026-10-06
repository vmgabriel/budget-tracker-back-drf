"""Tasks application use cases."""

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

__all__ = (
    "AddTaskToDailyPlan",
    "CreateGoal",
    "CreateTask",
    "DeleteGoal",
    "DeleteTask",
    "GetDailyPlan",
    "GetGoal",
    "GetOrCreateDailyPlan",
    "GetTask",
    "LinkTaskToGoal",
    "ListDailyPlans",
    "ListUserGoals",
    "ListUserTasks",
    "MarkTaskAsDoing",
    "MarkTaskAsDone",
    "PromoteTaskPriority",
    "RemoveTaskFromDailyPlan",
    "UnlinkTaskFromGoal",
    "UpdateGoal",
    "UpdateTask",
)
