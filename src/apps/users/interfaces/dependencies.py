"""Composition of user use cases and their infrastructure adapters."""

from dataclasses import dataclass

from apps.users.application.use_cases import (
    AdminUpdateUser,
    AuthenticateUser,
    ChangeUserPlan,
    CreateUser,
    GetUser,
    ListUsers,
)
from apps.users.infrastructure.persistence.repositories import DjangoUserRepository
from apps.users.infrastructure.security import DjangoPasswordHasher
from shared.infrastructure.clock import SystemClock


@dataclass(frozen=True, slots=True)
class UserUseCases:
    create: CreateUser
    get: GetUser
    list: ListUsers
    admin_update: AdminUpdateUser
    change_plan: ChangeUserPlan


@dataclass(frozen=True, slots=True)
class AuthenticationUseCases:
    authenticate: AuthenticateUser


def build_user_use_cases() -> UserUseCases:
    repository = DjangoUserRepository()
    password_hasher = DjangoPasswordHasher()
    clock = SystemClock()
    return UserUseCases(
        create=CreateUser(repository, password_hasher, clock),
        get=GetUser(repository),
        list=ListUsers(repository),
        admin_update=AdminUpdateUser(repository, clock),
        change_plan=ChangeUserPlan(repository, clock),
    )


def build_authentication_use_cases() -> AuthenticationUseCases:
    """Build credential validation services without a session dependency."""
    repository = DjangoUserRepository()
    return AuthenticationUseCases(
        authenticate=AuthenticateUser(repository, DjangoPasswordHasher()),
    )
