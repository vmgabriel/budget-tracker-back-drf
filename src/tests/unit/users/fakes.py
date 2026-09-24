"""In-memory test doubles for user application ports."""

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from apps.users.domain.entities import User
from apps.users.domain.value_objects import Email, FullName, PasswordHash, UserId

FIXED_NOW = datetime(2025, 1, 1, tzinfo=UTC)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[UserId, User] = {}

    def add(self, user: User) -> User:
        if user.id is None:
            user.id = UserId(uuid4())
        self.users[user.id] = user
        return user

    def get_by_email(self, email: Email) -> User | None:
        return next(
            (user for user in self.users.values() if user.email == email),
            None,
        )

    def get_by_id(self, user_id: UserId) -> User | None:
        return self.users.get(user_id)

    def update(self, user: User) -> User:
        if user.id is None:
            raise ValueError("Cannot update an unidentified user.")
        self.users[user.id] = user
        return user

    def list(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        ordered = sorted(self.users.values(), key=lambda item: item.email.value)
        return ordered[offset : offset + limit], len(ordered)


class FakePasswordHasher:
    def __init__(self) -> None:
        self.hashed_passwords: list[str] = []

    def hash(self, raw_password: str) -> str:
        self.hashed_passwords.append(raw_password)
        return f"encoded:{raw_password}"

    def verify(self, raw_password: str, encoded_password: str) -> bool:
        return encoded_password == f"encoded:{raw_password}"


class FakeClock:
    def now(self) -> datetime:
        return FIXED_NOW

    def today(self) -> date:
        return FIXED_NOW.date()


class FakeSession:
    def __init__(self) -> None:
        self.logged_in_id: UserId | None = None
        self.logout_calls = 0

    def login(self, user_id: UserId) -> None:
        self.logged_in_id = user_id

    def logout(self) -> None:
        self.logged_in_id = None
        self.logout_calls += 1


def make_user(
    *,
    user_id: UUID | None = None,
    email: str = "person@example.com",
    password: str = "secret-password",
    is_active: bool = True,
) -> User:
    user = User.create(
        email=Email(email),
        password_hash=PasswordHash(f"encoded:{password}"),
        full_name=FullName("Test Person"),
        now=FIXED_NOW,
    )
    user.id = UserId(user_id or uuid4())
    user.is_active = is_active
    return user
