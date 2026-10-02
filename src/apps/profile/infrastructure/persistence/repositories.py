"""Django ORM implementation of the profile repository port."""

from django.db import transaction as db_transaction

from apps.profile.application.ports.repositories import ProfileRepository
from apps.profile.domain.entities import Profile
from apps.profile.domain.exceptions import ProfileNotFound
from apps.profile.domain.value_objects import (
    AvatarUrl,
    Bio,
    Currency,
    DateFormat,
    FullName,
    Language,
    ProfileId,
    Timezone,
    UserId,
)
from apps.profile.infrastructure.persistence.models import ProfileModel


class DjangoProfileRepository(ProfileRepository):
    """Persist and retrieve profile aggregates with the Django ORM."""

    def get_by_user_id(self, user_id: UserId) -> Profile | None:
        model = ProfileModel.objects.filter(user_id=user_id.value).first()
        return self._to_domain(model) if model is not None else None

    def save(self, profile: Profile) -> Profile:
        model = self._to_model(profile)
        with db_transaction.atomic():
            model.save(force_insert=True)
        return self._to_domain(model)

    def update(self, profile: Profile) -> Profile:
        if profile.id is None:
            raise ValueError("A persisted profile must have an identity.")
        model = ProfileModel.objects.filter(
            pk=profile.id.value,
            user_id=profile.user_id.value,
        ).first()
        if model is None:
            raise ProfileNotFound("Profile not found.")
        model.first_name = profile.full_name.first_name
        model.last_name = profile.full_name.last_name
        model.timezone = profile.timezone.value
        model.language = profile.language.value
        model.currency = profile.currency.value
        model.date_format = profile.date_format.value
        model.avatar_url = profile.avatar_url.value if profile.avatar_url else None
        model.bio = profile.bio.value if profile.bio else None
        with db_transaction.atomic():
            model.save(
                update_fields=(
                    "first_name",
                    "last_name",
                    "timezone",
                    "language",
                    "currency",
                    "date_format",
                    "avatar_url",
                    "bio",
                    "updated_at",
                )
            )
        return self._to_domain(model)

    @staticmethod
    def _to_model(profile: Profile) -> ProfileModel:
        return ProfileModel(
            id=profile.id.value if profile.id is not None else None,
            user_id=profile.user_id.value,
            first_name=profile.full_name.first_name,
            last_name=profile.full_name.last_name,
            timezone=profile.timezone.value,
            language=profile.language.value,
            currency=profile.currency.value,
            date_format=profile.date_format.value,
            avatar_url=profile.avatar_url.value if profile.avatar_url else None,
            bio=profile.bio.value if profile.bio else None,
        )

    @staticmethod
    def _to_domain(model: ProfileModel) -> Profile:
        return Profile(
            id=ProfileId(model.id),
            user_id=UserId(model.user_id),
            full_name=FullName(model.first_name, model.last_name),
            timezone=Timezone(model.timezone),
            language=Language(model.language),
            currency=Currency(model.currency),
            date_format=DateFormat(model.date_format),
            avatar_url=AvatarUrl(model.avatar_url) if model.avatar_url else None,
            bio=Bio(model.bio) if model.bio else None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
