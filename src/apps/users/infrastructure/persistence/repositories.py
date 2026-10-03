"""Django ORM implementation of the user repository port."""

from django.db import IntegrityError, transaction

from apps.users.application.ports.repositories import UserRepository
from apps.users.domain.entities import User
from apps.users.domain.exceptions import EmailAlreadyExists, UserNotFound
from apps.users.domain.value_objects import (
    BanReason,
    Email,
    FullName,
    PasswordHash,
    PlanLevel,
    UserId,
)
from apps.users.infrastructure.persistence.models import User as UserModel


class DjangoUserRepository(UserRepository):
    """Persist and retrieve user aggregates with the Django ORM."""

    def add(self, user: User) -> User:
        model = self._to_model(user)
        try:
            with transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as exc:
            raise EmailAlreadyExists("A user with this email already exists.") from exc
        return self._to_domain(model)

    def get_by_email(self, email: Email) -> User | None:
        model = UserModel.objects.filter(email__iexact=email.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_id(self, user_id: UserId) -> User | None:
        model = UserModel.objects.filter(pk=user_id.value).first()
        return self._to_domain(model) if model is not None else None

    def update(self, user: User) -> User:
        if user.id is None:
            raise ValueError("A persisted user must have an identity.")
        model = UserModel.objects.filter(pk=user.id.value).first()
        if model is None:
            raise UserNotFound("User not found.")
        model.email = user.email.value
        model.full_name = user.full_name.value
        model.plan = user.plan.value
        model.is_active = user.is_active
        model.is_banned = user.is_banned
        model.ban_reason = user.ban_reason.value if user.ban_reason else None
        try:
            with transaction.atomic():
                model.save(
                    update_fields=(
                        "email",
                        "full_name",
                        "plan",
                        "is_active",
                        "is_banned",
                        "ban_reason",
                        "updated_at",
                    )
                )
        except IntegrityError as exc:
            raise EmailAlreadyExists("A user with this email already exists.") from exc
        return self._to_domain(model)

    def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        queryset = UserModel.objects.all()
        total = queryset.count()
        models = list(queryset.order_by("email")[offset : offset + limit])
        return [self._to_domain(model) for model in models], total

    @staticmethod
    def _to_model(user: User) -> UserModel:
        return UserModel(
            id=user.id.value if user.id is not None else None,
            email=user.email.value,
            full_name=user.full_name.value,
            password=user.password_hash.value,
            plan=user.plan.value,
            is_active=user.is_active,
            is_staff=user.is_staff,
            is_superuser=user.is_superuser,
            is_banned=user.is_banned,
            ban_reason=user.ban_reason.value if user.ban_reason else None,
        )

    @staticmethod
    def _to_domain(model: UserModel) -> User:
        return User(
            id=UserId(model.id),
            email=Email(model.email),
            password_hash=PasswordHash(model.password),
            full_name=FullName(model.full_name),
            plan=PlanLevel(model.plan),
            is_active=model.is_active,
            is_staff=model.is_staff,
            is_superuser=model.is_superuser,
            created_at=model.date_joined,
            updated_at=model.updated_at,
            is_banned=model.is_banned,
            ban_reason=BanReason(model.ban_reason) if model.ban_reason else None,
        )
