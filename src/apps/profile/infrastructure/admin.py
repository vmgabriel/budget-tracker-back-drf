"""Django admin registration for profiles."""

from django.contrib import admin

from apps.profile.infrastructure.persistence.models import ProfileModel


@admin.register(ProfileModel)
class ProfileModelAdmin(admin.ModelAdmin):
    """Administrative profile browser."""

    list_display = (
        "id",
        "user",
        "first_name",
        "last_name",
        "language",
        "currency",
        "timezone",
    )
    list_filter = ("language", "currency", "date_format")
    list_select_related = ("user",)
    search_fields = ("first_name", "last_name", "user__email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("user__email",)
