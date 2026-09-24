"""Django ORM representation of the transaction aggregate."""

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.transactions.domain.value_objects import TRANSACTION_CHOICES, TransactionType

VALID_TRANSACTION_TYPES = tuple(item.value for item in TransactionType)


class Transaction(models.Model):
    """A financial transaction owned by an application user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(
        max_length=12,
        choices=TRANSACTION_CHOICES,
        default=TransactionType.EXPENSE.value,
    )
    category = models.CharField(max_length=100)
    date = models.DateField()
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="transaction_amount_gt_zero",
            ),
            models.CheckConstraint(
                condition=models.Q(transaction_type__in=VALID_TRANSACTION_TYPES),
                name="transaction_valid_type",
            ),
            models.CheckConstraint(
                condition=~models.Q(category__regex=r"^\s*$"),
                name="transaction_category_nonblank",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "-date", "-created_at", "-id"),
                name="transaction_owner_date_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.transaction_type.title()}: {self.amount}"
