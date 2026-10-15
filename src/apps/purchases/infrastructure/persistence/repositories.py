"""Django ORM implementations of the purchases repository ports.

Every adapter maps symmetrically between a model row and a domain entity, so
no persistence concern (blank strings, enum values, related managers) leaks into
the application layer.
"""

from datetime import datetime
from typing import Any

from django.db import IntegrityError
from django.db import transaction as db_transaction

from apps.purchases.application.ports.repositories import (
    ShoppingListItemRepository,
    ShoppingListRepository,
    TagRepository,
    WishlistItemRepository,
    WishlistRepository,
)
from apps.purchases.domain.entities import (
    ShoppingList,
    ShoppingListItem,
    Tag,
    Wishlist,
    WishlistItem,
)
from apps.purchases.domain.exceptions import (
    ShoppingListItemNotFound,
    ShoppingListNotFound,
    TagNotFound,
    WishlistAlreadyExists,
    WishlistItemNotFound,
    WishlistNotFound,
)
from apps.purchases.domain.value_objects import (
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
from apps.purchases.infrastructure.persistence.models import (
    ShoppingListItemModel,
    ShoppingListModel,
    TagModel,
    WishlistItemModel,
    WishlistModel,
)


def _tags_of(model: Any) -> list[Tag]:
    """Read the tag many-to-many of an item model into domain entities."""
    return [
        Tag(id=TagId(tag.pk), name=tag.name, slug=tag.slug) for tag in model.tags.all()
    ]


def _attach_tags(model: Any, tags: list[Tag]) -> None:
    """Replace the tag many-to-many of an item model with domain entities."""
    tag_ids = [tag.id.value for tag in tags if tag.id is not None]
    if tag_ids:
        model.tags.set(tag_ids)


class DjangoShoppingListRepository(ShoppingListRepository):
    """Persist and retrieve shopping lists with the Django ORM."""

    def get_by_id(self, shopping_list_id: ShoppingListId) -> ShoppingList | None:
        model = ShoppingListModel.objects.filter(pk=shopping_list_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_user_id(
        self, user_id: UserId, active_only: bool = True
    ) -> list[ShoppingList]:
        models = ShoppingListModel.objects.filter(user_id=user_id.value)
        if active_only:
            models = models.filter(is_active=True)
        return [self._to_domain(model) for model in models]

    def save(self, shopping_list: ShoppingList) -> ShoppingList:
        model = self._to_model(shopping_list)
        try:
            with db_transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as error:
            raise ShoppingListNotFound("Shopping list could not be created.") from error
        shopping_list.id = ShoppingListId(model.pk)
        return shopping_list

    def update(self, shopping_list: ShoppingList) -> ShoppingList:
        if shopping_list.id is None:
            raise ValueError("A persisted shopping list must have an identity.")
        model = ShoppingListModel.objects.filter(pk=shopping_list.id.value).first()
        if model is None:
            raise ShoppingListNotFound("Shopping list not found.")
        model.name = shopping_list.name
        model.priority = shopping_list.priority.value
        model.status = shopping_list.status.value
        model.is_active = shopping_list.is_active
        model.completed_at = shopping_list.completed_at
        model.save(
            update_fields=("name", "priority", "status", "is_active", "completed_at")
        )
        shopping_list.id = ShoppingListId(model.pk)
        return shopping_list

    def soft_delete(self, shopping_list_id: ShoppingListId) -> None:
        updated = ShoppingListModel.objects.filter(pk=shopping_list_id.value).update(
            is_active=False
        )
        if not updated:
            raise ShoppingListNotFound("Shopping list not found.")

    def restore(self, shopping_list_id: ShoppingListId) -> None:
        updated = ShoppingListModel.objects.filter(pk=shopping_list_id.value).update(
            is_active=True
        )
        if not updated:
            raise ShoppingListNotFound("Shopping list not found.")

    def get_archived_candidates(self, completed_before: datetime) -> list[ShoppingList]:
        """Return active lists already completed by ``completed_before``."""
        models = ShoppingListModel.objects.filter(
            is_active=True,
            status=ItemStatus.PURCHASED.value,
            completed_at__isnull=False,
            completed_at__lte=completed_before,
        )
        return [self._to_domain(model) for model in models]

    @staticmethod
    def _to_model(shopping_list: ShoppingList) -> ShoppingListModel:
        return ShoppingListModel(
            id=shopping_list.id.value if shopping_list.id is not None else None,
            user_id=shopping_list.user_id.value,
            name=shopping_list.name,
            priority=shopping_list.priority.value,
            status=shopping_list.status.value,
            is_active=shopping_list.is_active,
            created_at=shopping_list.created_at,
            completed_at=shopping_list.completed_at,
        )

    @staticmethod
    def _to_domain(model: ShoppingListModel) -> ShoppingList:
        return ShoppingList(
            id=ShoppingListId(model.pk),
            user_id=UserId(value=model.user_id),
            name=model.name,
            priority=ListPriority(model.priority),
            status=ItemStatus(model.status),
            is_active=model.is_active,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )


class DjangoWishlistRepository(WishlistRepository):
    """Persist and retrieve wishlists with the Django ORM."""

    def get_by_id(self, wishlist_id: WishlistId) -> Wishlist | None:
        model = WishlistModel.objects.filter(pk=wishlist_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_user_id(self, user_id: UserId) -> Wishlist | None:
        model = WishlistModel.objects.filter(user_id=user_id.value).first()
        return self._to_domain(model) if model is not None else None

    def save(self, wishlist: Wishlist) -> Wishlist:
        model = self._to_model(wishlist)
        try:
            with db_transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as error:
            # The unique constraint on ``user`` is what actually enforces
            # one-wishlist-per-user; two concurrent creations resolve here.
            raise WishlistAlreadyExists("This user already has a wishlist.") from error
        wishlist.id = WishlistId(model.pk)
        return wishlist

    def update(self, wishlist: Wishlist) -> Wishlist:
        if wishlist.id is None:
            raise ValueError("A persisted wishlist must have an identity.")
        model = WishlistModel.objects.filter(pk=wishlist.id.value).first()
        if model is None:
            raise WishlistNotFound("Wishlist not found.")
        model.name = wishlist.name
        model.status = wishlist.status.value
        model.is_active = wishlist.is_active
        model.completed_at = wishlist.completed_at
        model.save(update_fields=("name", "status", "is_active", "completed_at"))
        wishlist.id = WishlistId(model.pk)
        return wishlist

    def soft_delete(self, wishlist_id: WishlistId) -> None:
        updated = WishlistModel.objects.filter(pk=wishlist_id.value).update(
            is_active=False
        )
        if not updated:
            raise WishlistNotFound("Wishlist not found.")

    def restore(self, wishlist_id: WishlistId) -> None:
        updated = WishlistModel.objects.filter(pk=wishlist_id.value).update(
            is_active=True
        )
        if not updated:
            raise WishlistNotFound("Wishlist not found.")

    def get_archived_candidates(self, completed_before: datetime) -> list[Wishlist]:
        """Return active wishlists already completed by ``completed_before``."""
        models = WishlistModel.objects.filter(
            is_active=True,
            status=ItemStatus.PURCHASED.value,
            completed_at__isnull=False,
            completed_at__lte=completed_before,
        )
        return [self._to_domain(model) for model in models]

    @staticmethod
    def _to_model(wishlist: Wishlist) -> WishlistModel:
        return WishlistModel(
            id=wishlist.id.value if wishlist.id is not None else None,
            user_id=wishlist.user_id.value,
            name=wishlist.name,
            status=wishlist.status.value,
            is_active=wishlist.is_active,
            created_at=wishlist.created_at,
            completed_at=wishlist.completed_at,
        )

    @staticmethod
    def _to_domain(model: WishlistModel) -> Wishlist:
        return Wishlist(
            id=WishlistId(model.pk),
            user_id=UserId(value=model.user_id),
            name=model.name,
            status=ItemStatus(model.status),
            is_active=model.is_active,
            created_at=model.created_at,
            completed_at=model.completed_at,
        )


class DjangoShoppingListItemRepository(ShoppingListItemRepository):
    """Persist and retrieve shopping list items with the Django ORM."""

    def get_by_list_id(
        self, shopping_list_id: ShoppingListId
    ) -> list[ShoppingListItem]:
        models = ShoppingListItemModel.objects.filter(
            shopping_list_id=shopping_list_id.value
        ).prefetch_related("tags")
        return [self._to_domain(model) for model in models]

    def get_by_id(self, item_id: ShoppingListItemId) -> ShoppingListItem | None:
        model = (
            ShoppingListItemModel.objects.filter(pk=item_id.value)
            .prefetch_related("tags")
            .first()
        )
        return self._to_domain(model) if model is not None else None

    def save(self, item: ShoppingListItem) -> ShoppingListItem:
        model = self._to_model(item)
        try:
            with db_transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as error:
            raise ShoppingListItemNotFound(
                "Shopping list item could not be created."
            ) from error
        item.id = ShoppingListItemId(model.pk)
        _attach_tags(model, item.tags)
        return item

    def update(self, item: ShoppingListItem) -> ShoppingListItem:
        if item.id is None:
            raise ValueError("A persisted shopping list item must have an identity.")
        model = (
            ShoppingListItemModel.objects.filter(pk=item.id.value)
            .prefetch_related("tags")
            .first()
        )
        if model is None:
            raise ShoppingListItemNotFound("Shopping list item not found.")
        model.name = item.name
        model.quantity = int(item.quantity)
        model.details = item.details or ""
        model.status = item.status.value
        model.save(update_fields=("name", "quantity", "details", "status"))
        _attach_tags(model, item.tags)
        return item

    def delete(self, item_id: ShoppingListItemId) -> None:
        deleted, _ = ShoppingListItemModel.objects.filter(pk=item_id.value).delete()
        if not deleted:
            raise ShoppingListItemNotFound("Shopping list item not found.")

    @staticmethod
    def _to_model(item: ShoppingListItem) -> ShoppingListItemModel:
        return ShoppingListItemModel(
            id=item.id.value if item.id is not None else None,
            shopping_list_id=item.shopping_list_id.value,
            name=item.name,
            quantity=int(item.quantity),
            details=item.details or "",
            status=item.status.value,
        )

    @staticmethod
    def _to_domain(model: ShoppingListItemModel) -> ShoppingListItem:
        return ShoppingListItem(
            id=ShoppingListItemId(model.pk),
            shopping_list_id=ShoppingListId(model.shopping_list_id),
            name=model.name,
            quantity=Quantity(model.quantity),
            details=model.details or None,
            status=ItemStatus(model.status),
            tags=_tags_of(model),
        )


class DjangoWishlistItemRepository(WishlistItemRepository):
    """Persist and retrieve wishlist items with the Django ORM."""

    def get_by_wishlist_id(self, wishlist_id: WishlistId) -> list[WishlistItem]:
        models = WishlistItemModel.objects.filter(
            wishlist_id=wishlist_id.value
        ).prefetch_related("tags")
        return [self._to_domain(model) for model in models]

    def get_by_id(self, item_id: WishlistItemId) -> WishlistItem | None:
        model = (
            WishlistItemModel.objects.filter(pk=item_id.value)
            .prefetch_related("tags")
            .first()
        )
        return self._to_domain(model) if model is not None else None

    def save(self, item: WishlistItem) -> WishlistItem:
        model = self._to_model(item)
        try:
            with db_transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as error:
            raise WishlistItemNotFound("Wishlist item could not be created.") from error
        item.id = WishlistItemId(model.pk)
        _attach_tags(model, item.tags)
        return item

    def update(self, item: WishlistItem) -> WishlistItem:
        if item.id is None:
            raise ValueError("A persisted wishlist item must have an identity.")
        model = (
            WishlistItemModel.objects.filter(pk=item.id.value)
            .prefetch_related("tags")
            .first()
        )
        if model is None:
            raise WishlistItemNotFound("Wishlist item not found.")
        model.name = item.name
        model.link = str(item.link) if item.link is not None else ""
        model.image_link = str(item.image_link) if item.image_link is not None else ""
        model.description = item.description or ""
        model.estimated_price = (
            item.estimated_price.amount if item.estimated_price is not None else None
        )
        model.priority = item.priority.value
        model.status = item.status.value
        model.save(
            update_fields=(
                "name",
                "link",
                "image_link",
                "description",
                "estimated_price",
                "priority",
                "status",
            )
        )
        _attach_tags(model, item.tags)
        return item

    def delete(self, item_id: WishlistItemId) -> None:
        deleted, _ = WishlistItemModel.objects.filter(pk=item_id.value).delete()
        if not deleted:
            raise WishlistItemNotFound("Wishlist item not found.")

    @staticmethod
    def _to_model(item: WishlistItem) -> WishlistItemModel:
        return WishlistItemModel(
            id=item.id.value if item.id is not None else None,
            wishlist_id=item.wishlist_id.value,
            name=item.name,
            link=str(item.link) if item.link is not None else "",
            image_link=str(item.image_link) if item.image_link is not None else "",
            description=item.description or "",
            estimated_price=(
                item.estimated_price.amount
                if item.estimated_price is not None
                else None
            ),
            priority=item.priority.value,
            status=item.status.value,
        )

    @staticmethod
    def _to_domain(model: WishlistItemModel) -> WishlistItem:
        return WishlistItem(
            id=WishlistItemId(model.pk),
            wishlist_id=WishlistId(model.wishlist_id),
            name=model.name,
            link=Link(model.link) if model.link else None,
            image_link=Link(model.image_link) if model.image_link else None,
            description=model.description or None,
            estimated_price=(
                EstimatedPrice(model.estimated_price)
                if model.estimated_price is not None
                else None
            ),
            priority=WishlistPriority(model.priority),
            status=ItemStatus(model.status),
            tags=_tags_of(model),
        )


class DjangoTagRepository(TagRepository):
    """Persist and retrieve the tag catalogue with the Django ORM."""

    def get_by_id(self, tag_id: TagId) -> Tag | None:
        model = TagModel.objects.filter(pk=tag_id.value).first()
        return self._to_domain(model) if model is not None else None

    def get_by_name_or_slug(self, name_or_slug: str) -> Tag | None:
        candidate = str(name_or_slug).strip()
        model = TagModel.objects.filter(name__iexact=candidate).first()
        if model is None:
            model = TagModel.objects.filter(slug=candidate.lower()).first()
        return self._to_domain(model) if model is not None else None

    def get_or_create(self, name: str) -> Tag:
        existing = self.get_by_name_or_slug(name)
        if existing is not None:
            return existing
        model = TagModel(name=str(name).strip())
        try:
            with db_transaction.atomic():
                model.save(force_insert=True)
        except IntegrityError as error:
            # Another writer created the same tag first; adopt theirs so the
            # catalogue stays single-valued per name.
            existing = self.get_by_name_or_slug(name)
            if existing is None:
                raise TagNotFound("Tag not found.") from error
            return existing
        return self._to_domain(model)

    def list_all(self) -> list[Tag]:
        return [self._to_domain(model) for model in TagModel.objects.all()]

    @staticmethod
    def _to_domain(model: TagModel) -> Tag:
        return Tag(id=TagId(model.pk), name=model.name, slug=model.slug)
