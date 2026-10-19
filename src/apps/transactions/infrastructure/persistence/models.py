"""Django ORM representation of the transaction and account aggregates."""

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.transactions.domain.value_objects import (
    ACCOUNT_TYPE_CHOICES,
    TRANSACTION_CHOICES,
    AccountType,
    TransactionType,
)

VALID_TRANSACTION_TYPES = tuple(item.value for item in TransactionType)
VALID_ACCOUNT_TYPES = tuple(item.value for item in AccountType)


class Account(models.Model):
    """A funding source owned by an application user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="accounts",
    )
    name = models.CharField(max_length=100)
    account_type = models.CharField(
        max_length=12,
        choices=ACCOUNT_TYPE_CHOICES,
        default=AccountType.CASH.value,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(account_type__in=VALID_ACCOUNT_TYPES),
                name="account_valid_type",
            ),
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="account_name_nonblank",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "is_active", "name"),
                name="account_owner_active_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.account_type})"


class Transaction(models.Model):
    """A financial transaction owned by an application user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    account = models.ForeignKey(
        Account,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
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
            ),
            models.Index(
                fields=("user", "date", "transaction_type"),
                name="transaction_owner_type_idx",
            ),
            models.Index(
                fields=("account", "-date"),
                name="transaction_account_date_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.transaction_type.title()}: {self.amount}"
