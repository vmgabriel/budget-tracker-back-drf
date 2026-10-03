"""URL routes for the users bounded context."""

from django.urls import path

from apps.users.interfaces.views import (
    BanUserView,
    ChangeUserPlanView,
    CurrentUserView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    LogoutView,
    RegisterView,
    UserDetailView,
    UserListView,
)

app_name = "users"

urlpatterns = [
    # Authentication (JWT)
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="login"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="refresh"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    # User profile
    path("me/", CurrentUserView.as_view(), name="current-user"),
    # User management (admin/staff only)
    path("", UserListView.as_view(), name="user-list"),
    path("<uuid:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("<uuid:pk>/plan/", ChangeUserPlanView.as_view(), name="change-plan"),
    path("<uuid:pk>/ban/", BanUserView.as_view(), name="ban-user"),
]
