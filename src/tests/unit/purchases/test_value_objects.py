"""Purchases value-object tests."""

from dataclasses import FrozenInstanceError
from decimal import Decimal
from uuid import uuid4

import pytest

from apps.purchases.domain.exceptions import InvalidArchiveDelay
from apps.purchases.domain.value_objects import (
    DEFAULT_ARCHIVE_DELAY,
    ITEM_STATUS_CHOICES,
    LIST_PRIORITY_CHOICES,
    WISHLIST_PRIORITY_CHOICES,
    ArchiveDelay,
    EstimatedPrice,
    ItemStatus,
    Link,
    ListPriority,
    Quantity,
    ShoppingListId,
    ShoppingListItemId,
    TagId,
    UserId,
    WishlistId,
    WishlistItemId,
    WishlistPriority,
)

pytestmark = pytest.mark.unit

IDENTITY_TYPES = (
    (ShoppingListId, "ShoppingListId"),
    (WishlistId, "WishlistId"),
    (ShoppingListItemId, "ShoppingListItemId"),
    (WishlistItemId, "WishlistItemId"),
    (TagId, "TagId"),
    (UserId, "UserId"),
)


@pytest.mark.parametrize(("identity_type", "label"), IDENTITY_TYPES)
def test_identity_wraps_uuid_and_is_immutable(identity_type: type, label: str) -> None:
    identifier = identity_type(value=uuid4())

    assert str(identifier) == str(identifier.value)
    with pytest.raises(FrozenInstanceError):
        identifier.value = uuid4()
    with pytest.raises(TypeError, match=label):
        identity_type(value="not-a-uuid")


def test_enum_choices_cover_every_member() -> None:
    assert [value for value, _ in LIST_PRIORITY_CHOICES] == [
        priority.value for priority in ListPriority
    ]
    assert [value for value, _ in WISHLIST_PRIORITY_CHOICES] == [
        priority.value for priority in WishlistPriority
    ]
    assert [value for value, _ in ITEM_STATUS_CHOICES] == [
        status.value for status in ItemStatus
    ]


def test_archive_delay_defaults_to_seven_days() -> None:
    assert ArchiveDelay().days == DEFAULT_ARCHIVE_DELAY
    assert Decimal("7.0") == DEFAULT_ARCHIVE_DELAY


def test_archive_delay_accepts_fractions_and_zero() -> None:
    assert ArchiveDelay(0.5).days == Decimal("0.5")
    assert ArchiveDelay(0).days == Decimal("0")
    assert ArchiveDelay(Decimal("2.5")).days == Decimal("2.5")


@pytest.mark.parametrize("value", [-1, "-0.5", "abc", None, Decimal("NaN")])
def test_archive_delay_rejects_unusable_values(value: object) -> None:
    with pytest.raises(InvalidArchiveDelay):
        ArchiveDelay(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [1, 3, 9999])
def test_quantity_accepts_positive_integers(value: int) -> None:
    assert int(Quantity(value)) == value


@pytest.mark.parametrize("value", [0, -1, 10000, True, "2", 1.5])
def test_quantity_rejects_invalid_values(value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        Quantity(value=value)  # type: ignore[arg-type]


def test_estimated_price_accepts_zero_and_rejects_negative() -> None:
    assert EstimatedPrice(Decimal("0")).amount == Decimal("0")

    with pytest.raises(ValueError, match="cannot be negative"):
        EstimatedPrice(Decimal("-0.01"))
    with pytest.raises(ValueError, match="valid decimal"):
        EstimatedPrice("free")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must not exceed"):
        EstimatedPrice(Decimal("99999999999.99"))


def test_link_requires_http_url_with_host() -> None:
    assert str(Link(" https://example.com/item?a=1 ")) == "https://example.com/item?a=1"

    with pytest.raises(ValueError, match="empty"):
        Link("   ")
    with pytest.raises(ValueError, match="http or https"):
        Link("ftp://example.com")
    with pytest.raises(ValueError, match="valid host"):
        Link("https://")
    with pytest.raises(ValueError, match="cannot exceed"):
        Link(f"https://example.com/{'a' * 500}")
