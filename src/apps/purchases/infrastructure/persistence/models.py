"""Django ORM representations of the purchases aggregates."""

from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.purchases.domain.value_objects import (
    ITEM_STATUS_CHOICES,
    LIST_PRIORITY_CHOICES,
    MAX_ESTIMATED_PRICE,
    MAX_ITEM_DESCRIPTION_LENGTH,
    MAX_ITEM_DETAILS_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_LIST_NAME_LENGTH,
    MAX_QUANTITY,
    MAX_TAG_NAME_LENGTH,
    MAX_URL_LENGTH,
    WISHLIST_PRIORITY_CHOICES,
    ItemStatus,
    ListPriority,
    WishlistPriority,
)

VALID_ITEM_STATUSES = tuple(item.value for item in ItemStatus)
VALID_LIST_PRIORITIES = tuple(item.value for item in ListPriority)
VALID_WISHLIST_PRIORITIES = tuple(item.value for item in WishlistPriority)


class TagModel(models.Model):
    """A label from the tag catalogue, shared across items."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=MAX_TAG_NAME_LENGTH, unique=True)
    slug = models.SlugField(max_length=MAX_TAG_NAME_LENGTH, unique=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="tag_name_nonblank",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Derive the slug from the name on every write."""
        self.slug = slugify(self.name)[:MAX_TAG_NAME_LENGTH]
        super().save(*args, **kwargs)


class ShoppingListModel(models.Model):
    """A named group of things to buy, owned by a single user."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="shopping_lists",
    )
    name = models.CharField(max_length=MAX_LIST_NAME_LENGTH)
    priority = models.CharField(
        max_length=16, choices=LIST_PRIORITY_CHOICES, default=ListPriority.MEDIUM.value
    )
    status = models.CharField(
        max_length=16, choices=ITEM_STATUS_CHOICES, default=ItemStatus.PENDING.value
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="shopping_list_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_ITEM_STATUSES),
                name="shopping_list_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=VALID_LIST_PRIORITIES),
                name="shopping_list_priority_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("user", "is_active"), name="shopping_list_user_active_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ShoppingListItemModel(models.Model):
    """One thing to buy, belonging to exactly one shopping list."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    shopping_list = models.ForeignKey(
        ShoppingListModel,
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=MAX_ITEM_NAME_LENGTH)
    quantity = models.IntegerField(default=1)
    details = models.TextField(
        max_length=MAX_ITEM_DETAILS_LENGTH, blank=True, default=""
    )
    status = models.CharField(
        max_length=16, choices=ITEM_STATUS_CHOICES, default=ItemStatus.PENDING.value
    )
    tags = models.ManyToManyField(
        TagModel, related_name="shopping_list_items", blank=True
    )

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="shopping_list_item_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1)
                & models.Q(quantity__lte=MAX_QUANTITY),
                name="shopping_list_item_quantity_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_ITEM_STATUSES),
                name="shopping_list_item_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("shopping_list",), name="shopping_list_item_list_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.quantity}x {self.name}"


class WishlistModel(models.Model):
    """The single wishlist owned by a user.

    The one-to-one relation is the database-level guarantee behind the
    one-wishlist-per-user rule; the domain cannot enforce it alone.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist",
    )
    name = models.CharField(max_length=MAX_LIST_NAME_LENGTH)
    status = models.CharField(
        max_length=16, choices=ITEM_STATUS_CHOICES, default=ItemStatus.PENDING.value
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="wishlist_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_ITEM_STATUSES),
                name="wishlist_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("user",), name="wishlist_user_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class WishlistItemModel(models.Model):
    """One wanted product, belonging to exactly one wishlist."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    wishlist = models.ForeignKey(
        WishlistModel,
        on_delete=models.CASCADE,
        related_name="items",
    )
    name = models.CharField(max_length=MAX_ITEM_NAME_LENGTH)
    link = models.URLField(max_length=MAX_URL_LENGTH, blank=True, default="")
    image_link = models.URLField(max_length=MAX_URL_LENGTH, blank=True, default="")
    description = models.TextField(
        max_length=MAX_ITEM_DESCRIPTION_LENGTH, blank=True, default=""
    )
    estimated_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=WISHLIST_PRIORITY_CHOICES,
        default=WishlistPriority.WANTED.value,
    )
    status = models.CharField(
        max_length=16, choices=ITEM_STATUS_CHOICES, default=ItemStatus.PENDING.value
    )
    tags = models.ManyToManyField(TagModel, related_name="wishlist_items", blank=True)

    class Meta:
        ordering = ("name", "id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="wishlist_item_name_nonblank",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_price__isnull=True)
                | models.Q(estimated_price__gte=0),
                name="wishlist_item_price_nonnegative",
            ),
            models.CheckConstraint(
                condition=models.Q(estimated_price__isnull=True)
                | models.Q(estimated_price__lte=MAX_ESTIMATED_PRICE),
                name="wishlist_item_price_max",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=VALID_WISHLIST_PRIORITIES),
                name="wishlist_item_priority_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=VALID_ITEM_STATUSES),
                name="wishlist_item_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=("wishlist",), name="wishlist_item_wishlist_idx"),
        ]

    def __str__(self) -> str:
        return self.name
