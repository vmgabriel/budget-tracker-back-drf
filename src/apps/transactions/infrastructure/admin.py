"""Django admin registration for transactions and funding accounts."""

from django.contrib import admin

from apps.transactions.infrastructure.persistence.models import Account, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    """Administrative funding-account browser."""

    list_display = ("id", "user", "name", "account_type", "is_active")
    list_filter = ("account_type", "is_active")
    list_select_related = ("user",)
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("name", "id")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Administrative transaction browser."""

    list_display = (
        "id",
        "user",
        "account",
        "transaction_type",
        "amount",
        "category",
        "date",
    )
    list_filter = ("transaction_type", "date", "category")
    list_select_related = ("user", "account")
    search_fields = ("category", "description", "user__email")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-date", "-created_at", "-id")
