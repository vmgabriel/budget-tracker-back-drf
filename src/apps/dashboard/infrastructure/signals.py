"""Enqueue dashboard invalidation after committed transaction changes."""

import logging
from datetime import date
from uuid import UUID

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.dashboard.domain.value_objects import utc_to_local_date
from apps.dashboard.infrastructure.tasks import invalidate_user_dashboard_cache
from apps.profile.infrastructure.persistence.models import ProfileModel
from apps.transactions.infrastructure.persistence.models import Transaction

logger = logging.getLogger(__name__)

_PREVIOUS_DATE_ATTRIBUTE = "_dashboard_previous_date"
_PREVIOUS_USER_ATTRIBUTE = "_dashboard_previous_user_id"


@receiver(pre_save, sender=Transaction, dispatch_uid="dashboard_capture_old_date")
def capture_previous_transaction_date(
    sender: type[Transaction],
    instance: Transaction,
    **kwargs: object,
) -> None:
    """Remember the old date so moving a transaction refreshes both periods."""
    del kwargs
    if instance.pk is None:
        return
    previous_values = (
        sender.objects.filter(pk=instance.pk).values_list("date", "user_id").first()
    )
    if previous_values is not None:
        previous_date, previous_user_id = previous_values
        setattr(instance, _PREVIOUS_DATE_ATTRIBUTE, previous_date)
        setattr(instance, _PREVIOUS_USER_ATTRIBUTE, previous_user_id)


@receiver(post_save, sender=Transaction, dispatch_uid="dashboard_refresh_saved")
def refresh_after_transaction_save(
    sender: type[Transaction],
    instance: Transaction,
    raw: bool,
    **kwargs: object,
) -> None:
    """Schedule refreshes only after the surrounding database commit succeeds."""
    del sender, kwargs
    if raw:
        return
    affected_by_user: dict[UUID, set[date]] = {}
    affected_by_user[instance.user_id] = {instance.date} | _transaction_local_dates(
        instance, instance.user_id
    )
    previous_date = getattr(instance, _PREVIOUS_DATE_ATTRIBUTE, None)
    if isinstance(previous_date, date):
        affected_by_user[instance.user_id].add(previous_date)
    previous_user_id = getattr(instance, _PREVIOUS_USER_ATTRIBUTE, None)
    if isinstance(previous_user_id, UUID):
        extra: set[date] = set()
        if isinstance(previous_date, date):
            extra.add(previous_date)
        extra |= _transaction_local_dates(instance, previous_user_id)
        affected_by_user.setdefault(previous_user_id, set()).update(extra)
    _enqueue_invalidation(affected_by_user)


@receiver(post_delete, sender=Transaction, dispatch_uid="dashboard_refresh_deleted")
def refresh_after_transaction_delete(
    sender: type[Transaction],
    instance: Transaction,
    **kwargs: object,
) -> None:
    """Schedule a refresh after a committed transaction deletion."""
    del sender, kwargs
    affected = {instance.date} | _transaction_local_dates(instance, instance.user_id)
    _enqueue_invalidation({instance.user_id: affected})


def _user_timezone(user_id: UUID) -> str:
    profile = ProfileModel.objects.filter(user_id=user_id).only("timezone").first()
    if profile is None or not profile.timezone:
        return "UTC"
    return profile.timezone


def _transaction_local_dates(instance: Transaction, user_id: UUID) -> set[date]:
    """Local calendar dates touched by the transaction's UTC timestamps."""
    local_dates: set[date] = set()
    timezone = _user_timezone(user_id)
    for moment in (instance.created_at, instance.updated_at):
        if moment is None:
            continue
        try:
            local_dates.add(utc_to_local_date(moment, timezone))
        except ValueError:
            logger.exception(
                "Could not convert transaction timestamp user_id=%s tz=%s",
                user_id,
                timezone,
            )
    return local_dates


def _enqueue_invalidation(affected_by_user: dict[UUID, set[date]]) -> None:
    def enqueue() -> None:
        for user_id in sorted(affected_by_user):
            affected_dates = affected_by_user[user_id]
            serialized_dates = sorted(value.isoformat() for value in affected_dates)
            try:
                invalidate_user_dashboard_cache.delay(str(user_id), serialized_dates)
            except Exception:
                # The database transaction has already committed. Do not turn a
                # successful write into a retry storm; scheduled reconciliation
                # repairs the dashboard if the broker is temporarily unavailable.
                logger.exception(
                    "Could not enqueue dashboard invalidation user_id=%s dates=%s",
                    user_id,
                    serialized_dates,
                )

    transaction.on_commit(enqueue)
