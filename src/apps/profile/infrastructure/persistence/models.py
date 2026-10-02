"""Django ORM representation of the profile aggregate."""

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.domain.value_objects import DATE_FORMAT_CHOICES, DateFormat

VALID_DATE_FORMATS = tuple(item.value for item in DateFormat)


class ProfileModel(models.Model):
    """Personal data and regional preferences owned by one user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    timezone = models.CharField(max_length=50, default=PROFILE_DEFAULTS.timezone.value)
    language = models.CharField(max_length=10, default=PROFILE_DEFAULTS.language.value)
    currency = models.CharField(max_length=10, default=PROFILE_DEFAULTS.currency.value)
    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default=PROFILE_DEFAULTS.date_format.value,
    )
    avatar_url = models.URLField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_format__in=VALID_DATE_FORMATS),
                name="profile_valid_date_format",
            ),
            models.CheckConstraint(
                condition=(
                    ~models.Q(first_name__regex=r"^\s*$")
                    | ~models.Q(last_name__regex=r"^\s*$")
                ),
                name="profile_name_nonblank",
            ),
        ]

    def __str__(self) -> str:
        return f"Profile for user {self.user_id}"
