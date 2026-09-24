"""Django-backed password hashing and system clock adapters."""

from datetime import UTC, datetime

from django.contrib.auth.hashers import check_password, make_password

from apps.users.application.ports.clock import Clock
from apps.users.application.ports.security import PasswordHasher


class DjangoPasswordHasher(PasswordHasher):
    """Use Django's current password hashing infrastructure."""

    def hash(self, raw_password: str) -> str:
        return make_password(raw_password)

    def verify(self, raw_password: str, encoded_password: str) -> bool:
        return check_password(raw_password, encoded_password)


class SystemClock(Clock):
    """Provide timezone-aware UTC timestamps."""

    def now(self) -> datetime:
        return datetime.now(UTC)
