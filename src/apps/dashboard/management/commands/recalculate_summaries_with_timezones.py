"""Recalculate daily/weekly/monthly summaries using each user's timezone."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from apps.dashboard.domain.value_objects import utc_to_local_date
from apps.dashboard.infrastructure.tasks import generate_monthly_summary
from apps.profile.infrastructure.persistence.models import ProfileModel
from shared.infrastructure.clock import SystemClock


class Command(BaseCommand):
    """Rebuild summaries over a recent window honoring profile timezones."""

    help = (
        "Idempotently rebuild dashboard summaries for the last N days, "
        "anchored to each user's local calendar."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help="Number of local calendar days to rebuild (default: 30).",
        )
        parser.add_argument(
            "--user-id",
            type=str,
            default=None,
            help="Optional UUID to rebuild for one user instead of all.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days = int(options["days"])
        if not 1 <= days <= 366:
            raise CommandError("--days must be between 1 and 366.")
        user_id_option = options.get("user_id")
        user_id: UUID | None = None
        if user_id_option:
            try:
                user_id = UUID(str(user_id_option))
            except ValueError as exc:
                raise CommandError("--user-id must be a valid UUID.") from exc

        clock = SystemClock()
        user_model = apps.get_model("users", "User")
        users = user_model.objects.filter(is_active=True)
        if user_id is not None:
            users = users.filter(pk=user_id)
            if not users.exists():
                raise CommandError("The requested active user does not exist.")

        jobs = 0
        for owner in users:
            profile = ProfileModel.objects.filter(user_id=owner.pk).first()
            timezone = profile.timezone if profile and profile.timezone else "UTC"
            local_today = utc_to_local_date(clock.now(), timezone)
            start_local = local_today - timedelta(days=days - 1)
            month_starts = sorted(
                {
                    (start_local + timedelta(days=offset)).replace(day=1)
                    for offset in range(days)
                }
            )
            for month_start in month_starts:
                generate_monthly_summary.run(str(owner.pk), month_start.isoformat())
                jobs += 1

        self.stdout.write(
            self.style.SUCCESS(f"Recalculated summaries with {jobs} monthly jobs.")
        )
