"""Django admin registration for pre-computed summaries."""

from django.contrib import admin

from apps.dashboard.infrastructure.persistence.models import DashboardSummary


@admin.register(DashboardSummary)
class DashboardSummaryAdmin(admin.ModelAdmin):
    """Administrative dashboard cache browser."""

    list_display = (
        "user",
        "period",
        "date",
        "total_income",
        "total_expense",
        "net_balance",
        "is_stale",
        "generated_at",
    )
    list_filter = ("period", "is_stale", "date")
    list_select_related = ("user",)
    search_fields = ("user__email",)
    date_hierarchy = "date"
    readonly_fields = ("generated_at", "stale_at", "updated_at")
    ordering = ("-date", "period")
