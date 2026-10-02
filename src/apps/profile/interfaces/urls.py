"""URL routes for the profile bounded context."""

from django.urls import path

from apps.profile.interfaces.views import CurrentProfileView, UpdatePreferencesView

app_name = "profile"

urlpatterns = [
    path("me/", CurrentProfileView.as_view(), name="current-profile"),
    path(
        "me/preferences/",
        UpdatePreferencesView.as_view(),
        name="update-preferences",
    ),
]
