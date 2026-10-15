"""HTTP controllers for the purchases bounded context.

Every action follows the same shape: validate the payload with a serializer,
build a command, call one use case, render the safe result. Domain exceptions
never reach DRF unhandled - a missing or foreign resource becomes 404, invalid
input 400, and a second wishlist 409.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.exceptions import APIException, NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.purchases.application.commands import (
    AddItemToShoppingListCommand,
    AddItemToWishlistCommand,
    AddTagsToItemCommand,
    AddTagsToWishlistItemCommand,
    CreateShoppingListCommand,
    CreateTagCommand,
    DeleteShoppingListItemCommand,
    DeleteWishlistItemCommand,
    GetOrCreateWishlistCommand,
    GetShoppingListCommand,
    ListShoppingListsCommand,
    ListTagsCommand,
    MarkItemAsPurchasedCommand,
    MarkWishlistItemAsPurchasedCommand,
    RemoveTagsFromItemCommand,
    RemoveTagsFromWishlistItemCommand,
    RestoreShoppingListCommand,
    SoftDeleteShoppingListCommand,
    UpdateShoppingListCommand,
    UpdateShoppingListItemCommand,
    UpdateWishlistCommand,
    UpdateWishlistItemCommand,
)
from apps.purchases.application.exceptions import InvalidPurchasesInput
from apps.purchases.domain.exceptions import (
    InvalidArchiveDelay,
    ShoppingListItemNotFound,
    ShoppingListNotFound,
    TagNotFound,
    WishlistAlreadyExists,
    WishlistItemNotFound,
    WishlistNotFound,
)
from apps.purchases.interfaces.dependencies import build_purchases_use_cases
from apps.purchases.interfaces.serializers import (
    AddShoppingListItemSerializer,
    AddTagsSerializer,
    AddWishlistItemSerializer,
    CreateShoppingListSerializer,
    CreateTagSerializer,
    RemoveTagsSerializer,
    ShoppingListItemSerializer,
    ShoppingListSerializer,
    TagSerializer,
    UpdateShoppingListItemSerializer,
    UpdateShoppingListSerializer,
    UpdateWishlistItemSerializer,
    UpdateWishlistSerializer,
    WishlistItemSerializer,
    WishlistSerializer,
)
from apps.users.interfaces.permissions import IsNotBanned
from config.serializers import ERROR_RESPONSES

NOT_FOUND_ERRORS = (
    ShoppingListNotFound,
    ShoppingListItemNotFound,
    WishlistNotFound,
    WishlistItemNotFound,
    TagNotFound,
)

INPUT_ERRORS = (InvalidPurchasesInput, InvalidArchiveDelay)


class ConflictError(APIException):
    """Report a request that clashes with existing state.

    DRF ships no 409 exception, so the purchases context defines one: the
    one-wishlist-per-user rule is exactly that kind of clash.
    """

    status_code = status.HTTP_409_CONFLICT
    # Typed loosely because DRF annotates this as its lazy translation proxy.
    default_detail: Any = "The request conflicts with the current state."
    default_code = "conflict"


def _authenticated_user_id(request: Request) -> UUID:
    user_id = request.user.pk
    if not isinstance(user_id, UUID):
        raise ValidationError({"detail": "Authenticated identity is invalid."})
    return user_id


def _translate_purchases_error(exc: Exception) -> APIException:
    if isinstance(exc, NOT_FOUND_ERRORS):
        return NotFound(str(exc))
    if isinstance(exc, WishlistAlreadyExists):
        return ConflictError(str(exc))
    if isinstance(exc, INPUT_ERRORS):
        return ValidationError({"detail": str(exc)})
    return ValidationError({"detail": "The request could not be processed."})


@contextmanager
def translated_errors() -> Iterator[None]:
    """Map application and domain failures onto DRF exceptions.

    Every use-case call is wrapped in this, so no controller has to repeat the
    mapping and no domain exception can reach DRF unhandled.
    """
    try:
        yield
    except (APIException, ValidationError):
        raise
    except Exception as error:  # noqa: BLE001 - deliberately broad
        raise _translate_purchases_error(error) from error


def _validated[S: serializers.Serializer](
    serializer_class: type[S], request: Request
) -> dict[str, Any]:
    """Validate a request body and return the cleaned primitives."""
    serializer = serializer_class(data=request.data)
    serializer.is_valid(raise_exception=True)
    return dict(serializer.validated_data)


class ShoppingListListView(APIView):
    """List the authenticated user's active shopping lists or create one."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_lists_list",
        responses={
            status.HTTP_200_OK: ShoppingListSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request) -> Response:
        use_cases = build_purchases_use_cases()
        results = use_cases.list_user_shopping_lists.execute(
            ListShoppingListsCommand(user_id=_authenticated_user_id(request))
        )
        return Response(ShoppingListSerializer(results, many=True).data)

    @extend_schema(
        operation_id="purchases_shopping_lists_create",
        request=CreateShoppingListSerializer,
        responses={
            status.HTTP_201_CREATED: ShoppingListSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request) -> Response:
        payload = _validated(CreateShoppingListSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.create_shopping_list.execute(
                CreateShoppingListCommand(
                    user_id=_authenticated_user_id(request),
                    name=str(payload["name"]),
                    priority=str(payload.get("priority") or "medium"),
                )
            )
        return Response(
            ShoppingListSerializer(result).data, status=status.HTTP_201_CREATED
        )


class ShoppingListDetailView(APIView):
    """Retrieve, update, or soft-delete one shopping list."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_lists_retrieve",
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request, pk: UUID) -> Response:
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.get_shopping_list.execute(
                GetShoppingListCommand(
                    list_id=pk, user_id=_authenticated_user_id(request)
                )
            )
        return Response(ShoppingListSerializer(result).data)

    @extend_schema(
        operation_id="purchases_shopping_lists_partial_update",
        request=UpdateShoppingListSerializer,
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request, pk: UUID) -> Response:
        payload = _validated(UpdateShoppingListSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.update_shopping_list.execute(
                UpdateShoppingListCommand(
                    list_id=pk,
                    user_id=_authenticated_user_id(request),
                    name=_optional_str(payload.get("name")),
                    priority=_optional_str(payload.get("priority")),
                )
            )
        return Response(ShoppingListSerializer(result).data)

    @extend_schema(
        operation_id="purchases_shopping_lists_destroy",
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, pk: UUID) -> Response:
        """Soft-delete the list: the items survive and the list can be restored."""
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.soft_delete_shopping_list.execute(
                SoftDeleteShoppingListCommand(
                    list_id=pk, user_id=_authenticated_user_id(request)
                )
            )
        return Response(ShoppingListSerializer(result).data)


class InactiveShoppingListListView(APIView):
    """List the soft-deleted shopping lists of the authenticated user."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_lists_list_inactive",
        responses={
            status.HTTP_200_OK: ShoppingListSerializer(many=True),
            **ERROR_RESPONSES,
        },
    )
    def get(self, request: Request) -> Response:
        use_cases = build_purchases_use_cases()
        results = use_cases.list_inactive_shopping_lists.execute(
            ListShoppingListsCommand(user_id=_authenticated_user_id(request))
        )
        return Response(ShoppingListSerializer(results, many=True).data)


class RestoreShoppingListView(APIView):
    """Bring a soft-deleted shopping list back."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_lists_restore",
        request=None,
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.restore_shopping_list.execute(
                RestoreShoppingListCommand(
                    list_id=pk, user_id=_authenticated_user_id(request)
                )
            )
        return Response(ShoppingListSerializer(result).data)


class ShoppingListAddItemView(APIView):
    """Add an item to a shopping list."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_lists_add_item",
        request=AddShoppingListItemSerializer,
        responses={status.HTTP_201_CREATED: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, pk: UUID) -> Response:
        payload = _validated(AddShoppingListItemSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.add_item_to_shopping_list.execute(
                AddItemToShoppingListCommand(
                    list_id=pk,
                    user_id=_authenticated_user_id(request),
                    name=str(payload["name"]),
                    quantity=int(payload.get("quantity") or 1),
                    details=_optional_str(payload.get("details")),
                )
            )
        return Response(
            ShoppingListSerializer(result).data, status=status.HTTP_201_CREATED
        )


class ShoppingListItemDetailView(APIView):
    """Update or delete one item of a shopping list."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_list_items_partial_update",
        request=UpdateShoppingListItemSerializer,
        responses={
            status.HTTP_200_OK: ShoppingListItemSerializer,
            **ERROR_RESPONSES,
        },
    )
    def patch(self, request: Request, pk: UUID, item_id: UUID) -> Response:
        """Update an item; ``pk`` scopes the owner, ``item_id`` the resource."""
        payload = _validated(UpdateShoppingListItemSerializer, request)
        _require_item_on_list(pk, item_id, _authenticated_user_id(request))
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.update_shopping_list_item.execute(
                UpdateShoppingListItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    name=_optional_str(payload.get("name")),
                    quantity=(
                        int(payload["quantity"]) if "quantity" in payload else None
                    ),
                    details=_optional_str(payload.get("details")),
                )
            )
        return Response(ShoppingListItemSerializer(result).data)

    @extend_schema(
        operation_id="purchases_shopping_list_items_destroy",
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, pk: UUID, item_id: UUID) -> Response:
        _require_item_on_list(pk, item_id, _authenticated_user_id(request))
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.delete_shopping_list_item.execute(
                DeleteShoppingListItemCommand(
                    item_id=item_id, user_id=_authenticated_user_id(request)
                )
            )
        return Response(ShoppingListSerializer(result).data)


class ShoppingListItemMarkPurchasedView(APIView):
    """Flag a shopping list item as bought."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_list_items_mark_purchased",
        request=None,
        responses={status.HTTP_200_OK: ShoppingListSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, pk: UUID, item_id: UUID) -> Response:
        _require_item_on_list(pk, item_id, _authenticated_user_id(request))
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.mark_item_as_purchased.execute(
                MarkItemAsPurchasedCommand(
                    item_id=item_id, user_id=_authenticated_user_id(request)
                )
            )
        return Response(ShoppingListSerializer(result).data)


class ShoppingListItemTagsView(APIView):
    """Associate or detach tags on a shopping list item."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_shopping_list_items_add_tags",
        request=AddTagsSerializer,
        responses={
            status.HTTP_200_OK: ShoppingListItemSerializer,
            **ERROR_RESPONSES,
        },
    )
    def post(self, request: Request, pk: UUID, item_id: UUID) -> Response:
        payload = _validated(AddTagsSerializer, request)
        _require_item_on_list(pk, item_id, _authenticated_user_id(request))
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.add_tags_to_item.execute(
                AddTagsToItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    tag_names=[str(name) for name in payload["tag_names"]],
                )
            )
        return Response(ShoppingListItemSerializer(result).data)

    @extend_schema(
        operation_id="purchases_shopping_list_items_remove_tags",
        request=RemoveTagsSerializer,
        responses={
            status.HTTP_200_OK: ShoppingListItemSerializer,
            **ERROR_RESPONSES,
        },
    )
    def delete(self, request: Request, pk: UUID, item_id: UUID) -> Response:
        payload = _validated(RemoveTagsSerializer, request)
        _require_item_on_list(pk, item_id, _authenticated_user_id(request))
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.remove_tags_from_item.execute(
                RemoveTagsFromItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    tag_ids=[UUID(str(tag_id)) for tag_id in payload["tag_ids"]],
                )
            )
        return Response(ShoppingListItemSerializer(result).data)


class WishlistView(APIView):
    """Retrieve or rename the authenticated user's single wishlist."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_wishlist_retrieve",
        responses={status.HTTP_200_OK: WishlistSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        """Return the wishlist, creating the single one on first access."""
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.get_or_create_wishlist.execute(
                GetOrCreateWishlistCommand(user_id=_authenticated_user_id(request))
            )
        return Response(WishlistSerializer(result).data)

    @extend_schema(
        operation_id="purchases_wishlist_partial_update",
        request=UpdateWishlistSerializer,
        responses={status.HTTP_200_OK: WishlistSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request) -> Response:
        payload = _validated(UpdateWishlistSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            current = use_cases.get_or_create_wishlist.execute(
                GetOrCreateWishlistCommand(user_id=_authenticated_user_id(request))
            )
            result = use_cases.update_wishlist.execute(
                UpdateWishlistCommand(
                    wishlist_id=current.id.value,
                    user_id=_authenticated_user_id(request),
                    name=_optional_str(payload.get("name")),
                )
            )
        return Response(WishlistSerializer(result).data)


class WishlistAddItemView(APIView):
    """Add an item to the authenticated user's wishlist."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_wishlist_add_item",
        request=AddWishlistItemSerializer,
        responses={status.HTTP_201_CREATED: WishlistSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        payload = _validated(AddWishlistItemSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            current = use_cases.get_or_create_wishlist.execute(
                GetOrCreateWishlistCommand(user_id=_authenticated_user_id(request))
            )
            result = use_cases.add_item_to_wishlist.execute(
                AddItemToWishlistCommand(
                    wishlist_id=current.id.value,
                    user_id=_authenticated_user_id(request),
                    name=str(payload["name"]),
                    link=_optional_str(payload.get("link")),
                    image_link=_optional_str(payload.get("image_link")),
                    description=_optional_str(payload.get("description")),
                    estimated_price=payload.get("estimated_price"),
                    priority=str(payload.get("priority") or "wanted"),
                )
            )
        return Response(WishlistSerializer(result).data, status=status.HTTP_201_CREATED)


class WishlistItemDetailView(APIView):
    """Update or delete one item of the wishlist."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_wishlist_items_partial_update",
        request=UpdateWishlistItemSerializer,
        responses={status.HTTP_200_OK: WishlistItemSerializer, **ERROR_RESPONSES},
    )
    def patch(self, request: Request, item_id: UUID) -> Response:
        payload = _validated(UpdateWishlistItemSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.update_wishlist_item.execute(
                UpdateWishlistItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    name=_optional_str(payload.get("name")),
                    link=_optional_str(payload.get("link")),
                    image_link=_optional_str(payload.get("image_link")),
                    description=_optional_str(payload.get("description")),
                    estimated_price=payload.get("estimated_price"),
                    priority=_optional_str(payload.get("priority")),
                )
            )
        return Response(WishlistItemSerializer(result).data)

    @extend_schema(
        operation_id="purchases_wishlist_items_destroy",
        responses={status.HTTP_200_OK: WishlistSerializer, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, item_id: UUID) -> Response:
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.delete_wishlist_item.execute(
                DeleteWishlistItemCommand(
                    item_id=item_id, user_id=_authenticated_user_id(request)
                )
            )
        return Response(WishlistSerializer(result).data)


class WishlistItemMarkPurchasedView(APIView):
    """Flag a wishlist item as bought."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_wishlist_items_mark_purchased",
        request=None,
        responses={status.HTTP_200_OK: WishlistSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, item_id: UUID) -> Response:
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.mark_wishlist_item_as_purchased.execute(
                MarkWishlistItemAsPurchasedCommand(
                    item_id=item_id, user_id=_authenticated_user_id(request)
                )
            )
        return Response(WishlistSerializer(result).data)


class WishlistItemTagsView(APIView):
    """Associate or detach tags on a wishlist item."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_wishlist_items_add_tags",
        request=AddTagsSerializer,
        responses={status.HTTP_200_OK: WishlistItemSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request, item_id: UUID) -> Response:
        payload = _validated(AddTagsSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.add_tags_to_wishlist_item.execute(
                AddTagsToWishlistItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    tag_names=[str(name) for name in payload["tag_names"]],
                )
            )
        return Response(WishlistItemSerializer(result).data)

    @extend_schema(
        operation_id="purchases_wishlist_items_remove_tags",
        request=RemoveTagsSerializer,
        responses={status.HTTP_200_OK: WishlistItemSerializer, **ERROR_RESPONSES},
    )
    def delete(self, request: Request, item_id: UUID) -> Response:
        payload = _validated(RemoveTagsSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.remove_tags_from_wishlist_item.execute(
                RemoveTagsFromWishlistItemCommand(
                    item_id=item_id,
                    user_id=_authenticated_user_id(request),
                    tag_ids=[UUID(str(tag_id)) for tag_id in payload["tag_ids"]],
                )
            )
        return Response(WishlistItemSerializer(result).data)


class TagListView(APIView):
    """List the shared tag catalogue or add an entry to it."""

    permission_classes = (IsAuthenticated, IsNotBanned)
    authentication_classes = (JWTAuthentication,)

    @extend_schema(
        operation_id="purchases_tags_list",
        responses={status.HTTP_200_OK: TagSerializer(many=True), **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        results = build_purchases_use_cases().list_tags.execute(ListTagsCommand())
        return Response(TagSerializer(results, many=True).data)

    @extend_schema(
        operation_id="purchases_tags_create",
        request=CreateTagSerializer,
        responses={status.HTTP_201_CREATED: TagSerializer, **ERROR_RESPONSES},
    )
    def post(self, request: Request) -> Response:
        payload = _validated(CreateTagSerializer, request)
        use_cases = build_purchases_use_cases()
        with translated_errors():
            result = use_cases.create_tag.execute(
                CreateTagCommand(name=str(payload["name"]))
            )
        return Response(TagSerializer(result).data, status=status.HTTP_201_CREATED)


def _optional_str(value: object) -> str | None:
    """Return a stripped string, or ``None`` when the field was not supplied."""
    if value is None:
        return None
    return str(value).strip() or None


def _require_item_on_list(pk: UUID, item_id: UUID, user_id: UUID) -> None:
    """Reject a nested item URL that points outside the addressed list.

    Without this check a caller could address ``/lists/A/items/B/`` with B
    belonging to a different list of their own, and the view would happily
    mutate B. Owner scoping already passed at this point; this only pins the
    nesting.
    """
    use_cases = build_purchases_use_cases()
    with translated_errors():
        shopping_list = use_cases.get_shopping_list.execute(
            GetShoppingListCommand(list_id=pk, user_id=user_id)
        )
    if any(item.id.value == item_id for item in shopping_list.items):
        return
    raise NotFound("Shopping list item not found.")
