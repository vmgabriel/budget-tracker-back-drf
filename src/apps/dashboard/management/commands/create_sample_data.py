"""Create deterministic local users, transactions, and dashboard summaries."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from apps.dashboard.application.use_cases import (
    GenerateDashboardSummary,
    GenerateDashboardSummaryCommand,
    InvalidateUserCache,
    InvalidateUserCacheCommand,
)
from apps.dashboard.domain.value_objects import Period
from apps.dashboard.infrastructure.persistence.repositories import (
    DjangoDashboardSummaryRepository,
    DjangoTransactionReadRepository,
)
from apps.transactions.infrastructure.persistence.models import Transaction
from apps.users.domain.value_objects import PlanLevel
from shared.infrastructure.clock import SystemClock

DEFAULT_PASSWORD = "SamplePassword123!"


@dataclass(frozen=True, slots=True)
class _SampleTransaction:
    date: date
    amount: Decimal
    transaction_type: str
    category: str
    description: str


class Command(BaseCommand):
    """Populate a local database with idempotent demonstration data."""

    help = (
        "Create three plan users, multi-month transactions, and pre-computed "
        "dashboard summaries for local development and demos."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--months",
            type=int,
            default=3,
            help="Number of calendar months to populate (default: 3, max: 24).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help="Password assigned to each sample user.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if settings.ENVIRONMENT == "production":
            raise CommandError("create_sample_data is disabled in production.")
        months = int(options["months"])
        password = str(options["password"])
        if not 1 <= months <= 24:
            raise CommandError("--months must be between 1 and 24.")
        if len(password) < 8:
            raise CommandError("--password must contain at least 8 characters.")

        clock = SystemClock()
        today = clock.today()
        start = _month_start(today, -(months - 1))
        user_model = get_user_model()
        created_transactions = 0
        with db_transaction.atomic():
            users = [
                self._get_or_create_user(
                    user_model,
                    email="demo-free@example.com",
                    full_name="Demo Free User",
                    plan=PlanLevel.FREE.value,
                    password=password,
                ),
                self._get_or_create_user(
                    user_model,
                    email="demo-pro@example.com",
                    full_name="Demo Pro User",
                    plan=PlanLevel.PRO.value,
                    password=password,
                ),
                self._get_or_create_user(
                    user_model,
                    email="demo-premium@example.com",
                    full_name="Demo Premium User",
                    plan=PlanLevel.PREMIUM.value,
                    password=password,
                ),
            ]
            for index, user in enumerate(users):
                created_transactions += self._create_transactions(
                    user_id=user.id,
                    start=start,
                    today=today,
                    variant=index,
                )

            for user in users:
                self._regenerate_summaries(user.id, start, today, clock)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created or refreshed sample data for {len(users)} users "
                f"({created_transactions} new transactions)."
            )
        )
        self.stdout.write("Sample login password: " + password)
        self.stdout.write(
            "Sample users: demo-free@example.com, demo-pro@example.com, demo-premium@example.com"
        )

    @staticmethod
    def _get_or_create_user(
        user_model: Any,
        *,
        email: str,
        full_name: str,
        plan: str,
        password: str,
    ) -> Any:
        user, _ = user_model.objects.get_or_create(
            email=email,
            defaults={"full_name": full_name, "plan": plan, "is_active": True},
        )
        user.full_name = full_name
        user.plan = plan
        user.is_active = True
        user.set_password(password)
        user.save(
            update_fields=("full_name", "plan", "is_active", "password", "updated_at")
        )
        return user

    @staticmethod
    def _create_transactions(
        *,
        user_id: Any,
        start: date,
        today: date,
        variant: int,
    ) -> int:
        samples = _sample_transactions(start, today, variant)
        existing_markers = set(
            Transaction.objects.filter(
                user_id=user_id,
                description__regex=r"^\[sample:",
            ).values_list("description", flat=True)
        )
        new_transactions = [
            Transaction(
                user_id=user_id,
                amount=sample.amount,
                transaction_type=sample.transaction_type,
                category=sample.category,
                date=sample.date,
                description=sample.description,
            )
            for sample in samples
            if sample.description not in existing_markers
        ]
        if new_transactions:
            Transaction.objects.bulk_create(new_transactions)
        return len(new_transactions)

    @staticmethod
    def _regenerate_summaries(
        user_id: Any,
        start: date,
        today: date,
        clock: SystemClock,
    ) -> None:
        repository = DjangoDashboardSummaryRepository()
        invalidate = InvalidateUserCache(repository, clock)
        generate = GenerateDashboardSummary(
            repository,
            DjangoTransactionReadRepository(),
            clock,
        )
        first_week = start - timedelta(days=start.weekday())
        dates = _date_range(first_week, today)
        invalidate.execute(InvalidateUserCacheCommand(user_id, dates))

        for summary_date in dates:
            generate.execute(
                GenerateDashboardSummaryCommand(user_id, Period.DAILY, summary_date)
            )

        for week_start in _date_range(first_week, today, step=timedelta(days=7)):
            generate.execute(
                GenerateDashboardSummaryCommand(user_id, Period.WEEKLY, week_start)
            )

        for month_start in _month_starts(start, today):
            generate.execute(
                GenerateDashboardSummaryCommand(user_id, Period.MONTHLY, month_start)
            )


def _sample_transactions(
    start: date, today: date, variant: int
) -> list[_SampleTransaction]:
    samples: list[_SampleTransaction] = []
    for month_start in _month_starts(start, today):
        last_day = month_start.replace(
            day=monthrange(month_start.year, month_start.month)[1]
        )
        candidates = (
            (
                month_start,
                Decimal("3200.00") + variant * Decimal("250.00"),
                "income",
                "Salary",
                "Monthly salary",
            ),
            (
                month_start + timedelta(days=1),
                Decimal("1250.00") + variant * Decimal("75.00"),
                "expense",
                "Housing",
                "Housing payment",
            ),
            (
                month_start + timedelta(days=4),
                Decimal("320.00") + variant * Decimal("20.00"),
                "expense",
                "Food",
                "Groceries",
            ),
            (
                month_start + timedelta(days=9),
                Decimal("500.00") + variant * Decimal("50.00"),
                "savings",
                "Savings",
                "Savings contribution",
            ),
            (
                last_day,
                Decimal("150.00") + variant * Decimal("10.00"),
                "investment",
                "Investment",
                "Long-term investment",
            ),
        )
        for index, (
            sample_date,
            amount,
            transaction_type,
            category,
            label,
        ) in enumerate(candidates):
            if sample_date > today:
                continue
            samples.append(
                _SampleTransaction(
                    date=sample_date,
                    amount=amount,
                    transaction_type=transaction_type,
                    category=category,
                    description=f"[sample:{variant}:{month_start:%Y-%m}:{index}:{label}]",
                )
            )
    return samples


def _date_range(
    start: date,
    end: date,
    *,
    step: timedelta = timedelta(days=1),
) -> tuple[date, ...]:
    values: list[date] = []
    cursor = start
    while cursor <= end:
        values.append(cursor)
        cursor += step
    return tuple(values)


def _month_starts(start: date, end: date) -> tuple[date, ...]:
    first = start.replace(day=1)
    values: list[date] = []
    cursor = first
    while cursor <= end:
        values.append(cursor)
        cursor = _month_start(cursor, 1)
    return tuple(values)


def _month_start(value: date, offset: int) -> date:
    month_index = value.year * 12 + value.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)
