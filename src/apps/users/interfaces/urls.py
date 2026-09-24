"""URL routes for the users bounded context."""

from django.urls import path

from apps.users.interfaces.views import (
    AdminUserDetailView,
    AdminUserListView,
    AdminUserPlanView,
    LoginView,
    LogoutView,
    MeView,
    RegisterView,
)

app_name = "users"

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    # Nested aliases keep the resource-oriented paths available while the
    # original /api/v1/auth/... paths remain backwards compatible.
    path("users/auth/register/", RegisterView.as_view(), name="register-nested"),
    path("users/auth/login/", LoginView.as_view(), name="login-nested"),
    path("users/auth/logout/", LogoutView.as_view(), name="logout-nested"),
    path("users/auth/me/", MeView.as_view(), name="me-nested"),
    path("users/", AdminUserListView.as_view(), name="admin-list"),
    path(
        "users/<uuid:user_id>/",
        AdminUserDetailView.as_view(),
        name="admin-detail",
    ),
    path(
        "users/<uuid:user_id>/plan/",
        AdminUserPlanView.as_view(),
        name="admin-plan",
    ),
]
