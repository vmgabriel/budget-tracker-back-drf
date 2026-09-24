"""Django session adapter implementing the application session port."""

from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.http import HttpRequest

from apps.users.application.ports.security import UserSession
from apps.users.domain.exceptions import UserNotFound
from apps.users.domain.value_objects import UserId
from apps.users.infrastructure.persistence.models import User


class DjangoUserSession(UserSession):
    """Bridge opaque application session operations to Django."""

    def __init__(self, request: HttpRequest) -> None:
        self._request = request

    def login(self, user_id: UserId) -> None:
        user = User.objects.filter(pk=user_id.value).first()
        if user is None:
            raise UserNotFound("User not found.")
        django_login(self._request, user)

    def logout(self) -> None:
        django_logout(self._request)
