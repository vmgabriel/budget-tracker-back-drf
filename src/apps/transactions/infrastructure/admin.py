"""Django admin registration for transactions."""

from django.contrib import admin

from apps.transactions.infrastructure.persistence.models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Administrative transaction browser."""

    list_display = (
        "id",
        "user",
        "transaction_type",
        "amount",
        "category",
        "date",
    )
    list_filter = ("transaction_type", "date", "category")
    list_select_related = ("user",)
    search_fields = ("category", "description", "user__email")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-date", "-created_at", "-id")
