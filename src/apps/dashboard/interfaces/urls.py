"""URL routes for pre-computed dashboard summaries."""

from django.urls import path

from apps.dashboard.domain.value_objects import Period
from apps.dashboard.interfaces.views import DashboardOverviewView, DashboardView

app_name = "dashboard"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("overview/", DashboardOverviewView.as_view(), name="overview"),
    path(
        "daily/",
        DashboardView.as_view(fixed_period=Period.DAILY),
        name="daily",
    ),
    path(
        "weekly/",
        DashboardView.as_view(fixed_period=Period.WEEKLY),
        name="weekly",
    ),
    path(
        "monthly/",
        DashboardView.as_view(fixed_period=Period.MONTHLY),
        name="monthly",
    ),
]
