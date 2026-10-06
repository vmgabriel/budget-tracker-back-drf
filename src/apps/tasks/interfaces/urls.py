"""URL routes for the tasks bounded context.

Routes are declared with explicit action maps instead of a router: the tasks
context exposes exactly these endpoints, and an explicit map keeps a handler
from being reachable under a name nobody reviewed.
"""

from django.urls import path

from apps.tasks.interfaces.views import DailyPlanViewSet, GoalViewSet, TaskViewSet

app_name = "tasks"

urlpatterns = [
    # Tasks
    path(
        "tasks/",
        TaskViewSet.as_view({"get": "list", "post": "create"}),
        name="task-list",
    ),
    path(
        "tasks/<uuid:pk>/",
        TaskViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="task-detail",
    ),
    path(
        "tasks/<uuid:pk>/mark-doing/",
        TaskViewSet.as_view({"post": "mark_doing"}),
        name="task-mark-doing",
    ),
    path(
        "tasks/<uuid:pk>/mark-done/",
        TaskViewSet.as_view({"post": "mark_done"}),
        name="task-mark-done",
    ),
    path(
        "tasks/<uuid:pk>/promote-priority/",
        TaskViewSet.as_view({"post": "promote_priority"}),
        name="task-promote-priority",
    ),
    # Goals
    path(
        "goals/",
        GoalViewSet.as_view({"get": "list", "post": "create"}),
        name="goal-list",
    ),
    path(
        "goals/<uuid:pk>/",
        GoalViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="goal-detail",
    ),
    path(
        "goals/<uuid:pk>/link-task/",
        GoalViewSet.as_view({"post": "link_task"}),
        name="goal-link-task",
    ),
    path(
        "goals/<uuid:pk>/unlink-task/",
        GoalViewSet.as_view({"post": "unlink_task"}),
        name="goal-unlink-task",
    ),
    # Daily plans
    path(
        "daily-plans/",
        DailyPlanViewSet.as_view({"get": "list", "post": "create"}),
        name="dailyplan-list",
    ),
    path(
        "daily-plans/<uuid:pk>/",
        DailyPlanViewSet.as_view(
            {"get": "retrieve", "patch": "partial_update", "delete": "destroy"}
        ),
        name="dailyplan-detail",
    ),
    path(
        "daily-plans/<uuid:pk>/add-task/",
        DailyPlanViewSet.as_view({"post": "add_task"}),
        name="dailyplan-add-task",
    ),
    path(
        "daily-plans/<uuid:pk>/remove-task/",
        DailyPlanViewSet.as_view({"post": "remove_task"}),
        name="dailyplan-remove-task",
    ),
]
