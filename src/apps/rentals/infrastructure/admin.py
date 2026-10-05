"""Django admin registration for rentals."""

from django.contrib import admin

from apps.rentals.infrastructure.persistence.models import (
    ApartmentModel,
    DocumentModel,
    HouseModel,
    PaymentRecordModel,
    UtilityReadingModel,
)


@admin.register(HouseModel)
class HouseAdmin(admin.ModelAdmin):
    """Administrative house browser."""

    list_display = ("id", "name", "owner", "city", "state", "country", "created_at")
    list_filter = ("country", "state")
    list_select_related = ("owner",)
    search_fields = ("name", "street", "city", "owner__email")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ApartmentModel)
class ApartmentAdmin(admin.ModelAdmin):
    """Administrative apartment browser."""

    list_display = ("id", "number", "house", "floor", "monthly_rent", "created_at")
    list_select_related = ("house",)
    search_fields = ("number", "house__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(DocumentModel)
class DocumentAdmin(admin.ModelAdmin):
    """Administrative document browser."""

    list_display = ("id", "document_type", "apartment", "uploaded_at")
    list_filter = ("document_type",)
    list_select_related = ("apartment",)
    search_fields = ("file_url", "description")


@admin.register(UtilityReadingModel)
class UtilityReadingAdmin(admin.ModelAdmin):
    """Administrative utility reading browser."""

    list_display = (
        "id",
        "utility_type",
        "apartment",
        "reading_date",
        "consumption",
        "total_cost",
    )
    list_filter = ("utility_type",)
    list_select_related = ("apartment",)
    date_hierarchy = "reading_date"


@admin.register(PaymentRecordModel)
class PaymentRecordAdmin(admin.ModelAdmin):
    """Administrative payment record browser."""

    list_display = ("id", "apartment", "payment_date", "amount", "status")
    list_filter = ("status",)
    list_select_related = ("apartment",)
    search_fields = ("notes", "apartment__number")
    date_hierarchy = "payment_date"
