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
from apps.profile.application.config import PROFILE_DEFAULTS
from apps.profile.infrastructure.persistence.models import ProfileModel
from apps.rentals.infrastructure.persistence.models import (
    ApartmentModel,
    DocumentModel,
    HouseModel,
    PaymentRecordModel,
    UtilityReadingModel,
)
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


class ProfileFactory(factory.django.DjangoModelFactory):
    """Customize the profile auto-provisioned for a new user.

    The ``post_save`` signal provisions a profile for every created user, so
    this factory updates that row with the declared attributes instead of
    inserting a duplicate that would violate the one-to-one constraint.
    """

    class Meta:
        model = ProfileModel

    user = factory.SubFactory(UserFactory)
    first_name = factory.Sequence(lambda number: f"Profile {number}")
    last_name = "Owner"
    timezone = PROFILE_DEFAULTS.timezone.value
    language = PROFILE_DEFAULTS.language.value
    currency = PROFILE_DEFAULTS.currency.value
    date_format = PROFILE_DEFAULTS.date_format.value
    avatar_url = None
    bio = None

    @classmethod
    def _create(
        cls, model_class: type[ProfileModel], *args: Any, **kwargs: Any
    ) -> ProfileModel:
        del args
        user = kwargs.pop("user")
        profile = model_class.objects.get(user=user)
        for field, value in kwargs.items():
            setattr(profile, field, value)
        profile.save()
        return profile


class HouseFactory(factory.django.DjangoModelFactory):
    """Create persisted houses owned by a user."""

    class Meta:
        model = HouseModel

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda number: f"House {number}")
    street = factory.Sequence(lambda number: f"{number} Main Street")
    city = "Springfield"
    state = "IL"
    country = "US"


class ApartmentFactory(factory.django.DjangoModelFactory):
    """Create persisted apartments inside a house."""

    class Meta:
        model = ApartmentModel

    house = factory.SubFactory(HouseFactory)
    number = factory.Sequence(lambda number: f"{number}A")
    floor = 1
    monthly_rent = Decimal("500.00")


class DocumentFactory(factory.django.DjangoModelFactory):
    """Create persisted documents attached to an apartment."""

    class Meta:
        model = DocumentModel

    apartment = factory.SubFactory(ApartmentFactory)
    document_type = "LEASE_CONTRACT"
    file_url = factory.Sequence(
        lambda number: f"https://files.example.com/doc{number}.pdf"
    )
    description = "Lease contract"


class UtilityReadingFactory(factory.django.DjangoModelFactory):
    """Create persisted utility readings with consistent calculations."""

    class Meta:
        model = UtilityReadingModel

    apartment = factory.SubFactory(ApartmentFactory)
    utility_type = "WATER"
    reading_date = date(2026, 1, 15)
    previous_reading = Decimal("100.00")
    current_reading = Decimal("120.50")
    consumption = Decimal("20.50")
    unit_cost = Decimal("0.5000")
    total_cost = Decimal("10.25")


class PaymentRecordFactory(factory.django.DjangoModelFactory):
    """Create persisted payment records for an apartment."""

    class Meta:
        model = PaymentRecordModel

    apartment = factory.SubFactory(ApartmentFactory)
    payment_date = date(2026, 1, 5)
    amount = Decimal("500.00")
    status = "PAID"
    notes = None
