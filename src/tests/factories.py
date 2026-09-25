"""Factory-boy factories for integration tests."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any, cast

import factory
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.dashboard.domain.value_objects import Period
from apps.dashboard.infrastructure.persistence.models import DashboardSummary
from apps.transactions.domain.value_objects import TransactionType
from apps.transactions.infrastructure.persistence.models import Transaction

User = get_user_model()


@pytest.fixture
def jwt_token_factory() -> Callable[[Any], str]:
    """Return an access token factory for a persisted Django user."""

    def _generate_token(user: Any) -> str:
        refresh = cast(Any, RefreshToken.for_user(user))
        return str(refresh.access_token)

    return _generate_token


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda number: f"user{number}@example.com")
    full_name = factory.Sequence(lambda number: f"Test User {number}")
    plan = "free"
    is_active = True
    is_staff = False
    is_superuser = False

    @factory.post_generation
    def password(
        user: object,
        create: bool,
        extracted: str | None,
        **kwargs: object,
    ) -> None:
        del kwargs
        user.set_password(extracted or "StrongPass123!")  # type: ignore[attr-defined]
        if create:
            user.save(update_fields=("password",))  # type: ignore[attr-defined]


class TransactionFactory(factory.django.DjangoModelFactory):
    """Create persisted transactions for infrastructure and API tests."""

    class Meta:
        model = Transaction

    user = factory.SubFactory(UserFactory)
    amount = Decimal("25.00")
    transaction_type = TransactionType.EXPENSE.value
    category = factory.Sequence(lambda number: f"Category {number}")
    date = date(2025, 1, 10)
    description = "Test transaction"


class DashboardSummaryFactory(factory.django.DjangoModelFactory):
    """Create persisted pre-computed dashboard summaries."""

    class Meta:
        model = DashboardSummary

    user = factory.SubFactory(UserFactory)
    period = Period.DAILY.value
    date = date(2025, 1, 10)
    total_income = Decimal("100.00")
    total_expense = Decimal("25.00")
    net_balance = factory.LazyAttribute(
        lambda summary: summary.total_income - summary.total_expense
    )
    is_stale = False
    generated_at = factory.LazyFunction(timezone.now)
    stale_at = None
