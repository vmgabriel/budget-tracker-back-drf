"""Enqueue dashboard invalidation after committed transaction changes."""

import logging
from datetime import date
from uuid import UUID

from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.dashboard.infrastructure.tasks import invalidate_user_dashboard_cache
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
    affected_dates = {instance.date}
    user_ids = {instance.user_id}
    previous_date = getattr(instance, _PREVIOUS_DATE_ATTRIBUTE, None)
    if isinstance(previous_date, date):
        affected_dates.add(previous_date)
    previous_user_id = getattr(instance, _PREVIOUS_USER_ATTRIBUTE, None)
    if isinstance(previous_user_id, UUID):
        user_ids.add(previous_user_id)
    _enqueue_invalidation(user_ids, affected_dates)


@receiver(post_delete, sender=Transaction, dispatch_uid="dashboard_refresh_deleted")
def refresh_after_transaction_delete(
    sender: type[Transaction],
    instance: Transaction,
    **kwargs: object,
) -> None:
    """Schedule a refresh after a committed transaction deletion."""
    del sender, kwargs
    _enqueue_invalidation({instance.user_id}, {instance.date})


def _enqueue_invalidation(user_ids: set[UUID], affected_dates: set[date]) -> None:
    serialized_dates = sorted(value.isoformat() for value in affected_dates)

    def enqueue() -> None:
        for user_id in sorted(user_ids):
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
