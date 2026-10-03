"""The user aggregate."""

from dataclasses import dataclass
from datetime import datetime

from apps.users.domain.exceptions import UserAlreadyBanned, UserNotBanned
from apps.users.domain.value_objects import (
    BanReason,
    Email,
    FullName,
    PasswordHash,
    PlanLevel,
    UserId,
)


@dataclass(eq=False, slots=True)
class User:
    """User identity and business state, independent of persistence concerns."""

    email: Email
    password_hash: PasswordHash
    full_name: FullName
    plan: PlanLevel
    is_active: bool
    is_staff: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime
    id: UserId | None = None
    is_banned: bool = False
    ban_reason: BanReason | None = None

    @classmethod
    def create(
        cls,
        *,
        email: Email,
        password_hash: PasswordHash,
        full_name: FullName,
        now: datetime,
    ) -> "User":
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("User timestamps must be timezone-aware.")
        return cls(
            id=None,
            email=email,
            password_hash=password_hash,
            full_name=full_name,
            plan=PlanLevel.FREE,
            is_active=True,
            is_staff=False,
            is_superuser=False,
            created_at=now,
            updated_at=now,
        )

    def update_profile(self, full_name: FullName, *, now: datetime) -> None:
        self._require_aware(now)
        self.full_name = full_name
        self.updated_at = now

    def change_email(self, email: Email, *, now: datetime) -> None:
        self._require_aware(now)
        self.email = email
        self.updated_at = now

    def change_plan(self, plan: PlanLevel, *, now: datetime) -> None:
        self._require_aware(now)
        self.plan = plan
        self.updated_at = now

    def change_active_state(self, is_active: bool, *, now: datetime) -> None:
        self._require_aware(now)
        self.is_active = is_active
        self.updated_at = now

    def ban(self, reason: BanReason, *, now: datetime) -> "User":
        self._require_aware(now)
        if self.is_banned:
            raise UserAlreadyBanned("User is already banned.")
        self.is_banned = True
        self.ban_reason = reason
        self.updated_at = now
        return self

    def unban(self, *, now: datetime) -> "User":
        self._require_aware(now)
        if not self.is_banned:
            raise UserNotBanned("User is not banned.")
        self.is_banned = False
        self.ban_reason = None
        self.updated_at = now
        return self

    @staticmethod
    def _require_aware(now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("User timestamps must be timezone-aware.")
