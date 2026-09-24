"""Factory-boy factories for integration tests."""

from datetime import date
from decimal import Decimal

import factory
from django.contrib.auth import get_user_model

from apps.transactions.domain.value_objects import TransactionType
from apps.transactions.infrastructure.persistence.models import Transaction

User = get_user_model()


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
