"""Django ORM representation of the user aggregate."""

from uuid import uuid4

from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.users.domain.value_objects import PLAN_CHOICES, PlanLevel
from apps.users.infrastructure.persistence.managers import UserManager


class User(AbstractUser):
    """Email-authenticated application user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    username = None  # type: ignore[assignment]
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    plan = models.CharField(
        max_length=16,
        choices=PLAN_CHOICES,
        default=PlanLevel.FREE.value,
    )
    updated_at = models.DateTimeField(auto_now=True)
    is_banned = models.BooleanField(default=False, db_index=True)
    ban_reason = models.CharField(max_length=500, blank=True, null=True)

    objects = UserManager()  # type: ignore[assignment,misc]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ("email",)

    def __str__(self) -> str:
        return self.email

    def clean(self) -> None:
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()
