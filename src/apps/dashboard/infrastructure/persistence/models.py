"""Django ORM representation of a pre-computed dashboard summary."""

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.dashboard.domain.value_objects import PERIOD_CHOICES, Period

VALID_PERIODS = tuple(period.value for period in Period)


class DashboardSummary(models.Model):
    """One user's cached financial totals for a calendar period."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dashboard_summaries",
    )
    period = models.CharField(max_length=8, choices=PERIOD_CHOICES)
    date = models.DateField()
    total_income = models.DecimalField(max_digits=18, decimal_places=2)
    total_expense = models.DecimalField(max_digits=18, decimal_places=2)
    net_balance = models.DecimalField(max_digits=18, decimal_places=2)
    is_stale = models.BooleanField(default=False)
    generated_at = models.DateTimeField(default=timezone.now)
    stale_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "period")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "period", "date"),
                name="dashboard_owner_period_date_unique",
            ),
            models.CheckConstraint(
                condition=Q(period__in=VALID_PERIODS),
                name="dashboard_valid_period",
            ),
            models.CheckConstraint(
                condition=Q(total_income__gte=0),
                name="dashboard_income_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(total_expense__gte=0),
                name="dashboard_expense_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(net_balance=F("total_income") - F("total_expense")),
                name="dashboard_net_matches_totals",
            ),
            models.CheckConstraint(
                condition=(
                    Q(is_stale=True, stale_at__isnull=False)
                    | Q(is_stale=False, stale_at__isnull=True)
                ),
                name="dashboard_stale_timestamp_consistent",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "is_stale", "period", "date"),
                name="dashboard_owner_stale_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user_id}: {self.period} {self.date}"
