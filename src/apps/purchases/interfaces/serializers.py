"""DRF input and output serializers for the purchases context.

Requests are validated here and nowhere else: these serializers turn a payload
into the primitives a command expects, and render the safe application results
back out. Nested output is driven by the DTOs, which already flattened the
aggregate, so the view never walks an entity.
"""

from rest_framework import serializers

from apps.purchases.domain.value_objects import (
    ITEM_STATUS_CHOICES,
    LIST_PRIORITY_CHOICES,
    MAX_ITEM_DESCRIPTION_LENGTH,
    MAX_ITEM_DETAILS_LENGTH,
    MAX_ITEM_NAME_LENGTH,
    MAX_LIST_NAME_LENGTH,
    MAX_QUANTITY,
    MAX_TAG_NAME_LENGTH,
    MAX_URL_LENGTH,
    WISHLIST_PRIORITY_CHOICES,
)


class TagSerializer(serializers.Serializer):
    """Represent a tag in the catalogue."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(max_length=MAX_TAG_NAME_LENGTH, read_only=True)
    slug = serializers.CharField(max_length=MAX_TAG_NAME_LENGTH, read_only=True)


class CreateTagSerializer(serializers.Serializer):
    """Validate the fields required to create a tag."""

    name = serializers.CharField(max_length=MAX_TAG_NAME_LENGTH, trim_whitespace=True)


class ShoppingListItemSerializer(serializers.Serializer):
    """Represent a shopping list item with its nested tags."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(max_length=MAX_ITEM_NAME_LENGTH, read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    details = serializers.CharField(read_only=True, allow_null=True)
    status = serializers.ChoiceField(choices=ITEM_STATUS_CHOICES, read_only=True)
    tags = TagSerializer(many=True, read_only=True)


class ShoppingListSerializer(serializers.Serializer):
    """Represent a shopping list with its nested items and tags."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(max_length=MAX_LIST_NAME_LENGTH, read_only=True)
    priority = serializers.ChoiceField(choices=LIST_PRIORITY_CHOICES, read_only=True)
    status = serializers.ChoiceField(choices=ITEM_STATUS_CHOICES, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    items = ShoppingListItemSerializer(many=True, read_only=True)
    tags = TagSerializer(many=True, read_only=True)


class CreateShoppingListSerializer(serializers.Serializer):
    """Validate the fields required to create a shopping list."""

    name = serializers.CharField(max_length=MAX_LIST_NAME_LENGTH, trim_whitespace=True)
    priority = serializers.ChoiceField(
        choices=LIST_PRIORITY_CHOICES, required=False, default="medium"
    )


class UpdateShoppingListSerializer(serializers.Serializer):
    """Validate a partial shopping list replacement."""

    name = serializers.CharField(
        max_length=MAX_LIST_NAME_LENGTH, trim_whitespace=True, required=False
    )
    priority = serializers.ChoiceField(choices=LIST_PRIORITY_CHOICES, required=False)

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide name or priority.")
        return attrs


class AddShoppingListItemSerializer(serializers.Serializer):
    """Validate the fields required to add a shopping list item."""

    name = serializers.CharField(max_length=MAX_ITEM_NAME_LENGTH, trim_whitespace=True)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_QUANTITY, default=1)
    details = serializers.CharField(
        max_length=MAX_ITEM_DETAILS_LENGTH, required=False, allow_blank=True
    )


class UpdateShoppingListItemSerializer(serializers.Serializer):
    """Validate a partial shopping list item replacement."""

    name = serializers.CharField(
        max_length=MAX_ITEM_NAME_LENGTH, trim_whitespace=True, required=False
    )
    quantity = serializers.IntegerField(
        min_value=1, max_value=MAX_QUANTITY, required=False
    )
    details = serializers.CharField(
        max_length=MAX_ITEM_DETAILS_LENGTH, required=False, allow_blank=True
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide name, quantity, or details.")
        return attrs


class AddTagsSerializer(serializers.Serializer):
    """Validate the tag names to associate with an item."""

    tag_names = serializers.ListField(
        child=serializers.CharField(
            max_length=MAX_TAG_NAME_LENGTH, trim_whitespace=True
        ),
        allow_empty=False,
    )


class RemoveTagsSerializer(serializers.Serializer):
    """Validate the tag identities to detach from an item."""

    tag_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class WishlistItemSerializer(serializers.Serializer):
    """Represent a wishlist item with its nested tags."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(max_length=MAX_ITEM_NAME_LENGTH, read_only=True)
    link = serializers.URLField(read_only=True, allow_null=True)
    image_link = serializers.URLField(read_only=True, allow_null=True)
    description = serializers.CharField(read_only=True, allow_null=True)
    estimated_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True
    )
    priority = serializers.ChoiceField(
        choices=WISHLIST_PRIORITY_CHOICES, read_only=True
    )
    status = serializers.ChoiceField(choices=ITEM_STATUS_CHOICES, read_only=True)
    tags = TagSerializer(many=True, read_only=True)


class WishlistSerializer(serializers.Serializer):
    """Represent the wishlist with its nested items."""

    id = serializers.UUIDField(source="id.value", read_only=True)
    name = serializers.CharField(max_length=MAX_LIST_NAME_LENGTH, read_only=True)
    status = serializers.ChoiceField(choices=ITEM_STATUS_CHOICES, read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    items = WishlistItemSerializer(many=True, read_only=True)


class UpdateWishlistSerializer(serializers.Serializer):
    """Validate a partial wishlist replacement."""

    name = serializers.CharField(
        max_length=MAX_LIST_NAME_LENGTH, trim_whitespace=True, required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError("Provide name.")
        return attrs


class AddWishlistItemSerializer(serializers.Serializer):
    """Validate the fields required to add a wishlist item."""

    name = serializers.CharField(max_length=MAX_ITEM_NAME_LENGTH, trim_whitespace=True)
    link = serializers.URLField(
        max_length=MAX_URL_LENGTH, required=False, allow_blank=True, allow_null=True
    )
    image_link = serializers.URLField(
        max_length=MAX_URL_LENGTH, required=False, allow_blank=True, allow_null=True
    )
    description = serializers.CharField(
        max_length=MAX_ITEM_DESCRIPTION_LENGTH, required=False, allow_blank=True
    )
    estimated_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )
    priority = serializers.ChoiceField(
        choices=WISHLIST_PRIORITY_CHOICES, required=False, default="wanted"
    )


class UpdateWishlistItemSerializer(serializers.Serializer):
    """Validate a partial wishlist item replacement."""

    name = serializers.CharField(
        max_length=MAX_ITEM_NAME_LENGTH, trim_whitespace=True, required=False
    )
    link = serializers.URLField(
        max_length=MAX_URL_LENGTH, required=False, allow_blank=True, allow_null=True
    )
    image_link = serializers.URLField(
        max_length=MAX_URL_LENGTH, required=False, allow_blank=True, allow_null=True
    )
    description = serializers.CharField(
        max_length=MAX_ITEM_DESCRIPTION_LENGTH, required=False, allow_blank=True
    )
    estimated_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        required=False,
        allow_null=True,
    )
    priority = serializers.ChoiceField(
        choices=WISHLIST_PRIORITY_CHOICES, required=False
    )

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        if not attrs:
            raise serializers.ValidationError(
                "Provide name, link, image_link, description, "
                "estimated_price, or priority."
            )
        return attrs
