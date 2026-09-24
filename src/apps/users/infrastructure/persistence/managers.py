"""Custom user manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager

if TYPE_CHECKING:
    from apps.users.infrastructure.persistence.models import User


class UserManager(BaseUserManager["User"]):
    """Create users identified and authenticated by email."""

    def create_user(
        self,
        email: str,
        password: str,
        full_name: str,
        **extra_fields: Any,
    ) -> User:
        if not email.strip():
            raise ValueError("Users must have an email address.")
        if not password:
            raise ValueError("Users must have a password.")
        if not full_name.strip():
            raise ValueError("Users must have a full name.")

        user = self.model(
            email=self.normalize_email(email).lower(),
            full_name=" ".join(full_name.split()),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str,
        full_name: str,
        **extra_fields: Any,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_superuser=True.")
        return self.create_user(email, password, full_name, **extra_fields)
