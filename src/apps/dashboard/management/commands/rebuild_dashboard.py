"""Synchronously rebuild dashboard summaries for a bounded date range."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from apps.dashboard.infrastructure.tasks import generate_monthly_summary
from shared.infrastructure.clock import SystemClock


class Command(BaseCommand):
    """Backfill summaries without requiring a running Celery worker."""

    help = (
        "Rebuild daily, weekly, and monthly summaries for active users over "
        "the requested number of calendar months."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--months",
            type=int,
            default=3,
            help="Number of calendar months to rebuild, including the current month.",
        )
        parser.add_argument(
            "--user-id",
            type=str,
            default=None,
            help="Optional UUID to rebuild for one user instead of all active users.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        months = int(options["months"])
        if not 1 <= months <= 120:
            raise CommandError("--months must be between 1 and 120.")
        user_id_option = options.get("user_id")
        if user_id_option:
            try:
                user_id = UUID(str(user_id_option))
            except ValueError as exc:
                raise CommandError("--user-id must be a valid UUID.") from exc
        else:
            user_id = None

        today = SystemClock().today()
        month_starts = _month_starts(today, months)
        user_model = apps.get_model("users", "User")
        users = user_model.objects.filter(is_active=True)
        if user_id is not None:
            users = users.filter(pk=user_id)
            if not users.exists():
                raise CommandError("The requested active user does not exist.")

        jobs = 0
        for user in users.iterator():
            for month_start in month_starts:
                generate_monthly_summary.run(str(user.pk), month_start.isoformat())
                jobs += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Rebuilt {jobs} monthly dashboard jobs through {today.isoformat()}."
            )
        )


def _month_starts(today: date, months: int) -> tuple[date, ...]:
    first = today.replace(day=1)
    return tuple(_shift_month(first, -offset) for offset in reversed(range(months)))


def _shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)
