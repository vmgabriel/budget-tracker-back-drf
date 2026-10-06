"""API v1 URL configuration - aggregates all app module URLs."""

from django.urls import include, path

app_name = "api_v1"

urlpatterns = [
    # User routes are mounted under the resource-oriented /api/v1/users/ prefix.
    path("users/", include("apps.users.interfaces.urls")),
    path("transactions/", include("apps.transactions.interfaces.urls")),
    path("dashboard/", include("apps.dashboard.interfaces.urls")),
    path("profile/", include("apps.profile.interfaces.urls")),
    path("rentals/", include("apps.rentals.interfaces.urls")),
    # Tasks, goals, and daily plans answer at the API root: the context name is
    # already carried by each resource, so a /tasks/tasks/ prefix would only
    # repeat itself.
    path("", include("apps.tasks.interfaces.urls")),
]
