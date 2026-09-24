"""Factory-boy factories for integration tests."""

import factory
from django.contrib.auth import get_user_model

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
