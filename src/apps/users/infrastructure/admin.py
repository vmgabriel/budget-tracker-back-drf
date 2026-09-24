"""Django admin registration for custom users."""

from django.contrib import admin

from apps.users.infrastructure.persistence.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2"),
            },
        ),
    )
    fieldsets = (
        (None, {"fields": ("email", "full_name", "password")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Plan", {"fields": ("plan",)}),
        ("Important dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    list_display = (
        "email",
        "full_name",
        "plan",
        "is_active",
        "is_staff",
        "date_joined",
    )
    list_filter = ("plan", "is_active", "is_staff", "is_superuser")
    list_select_related = ("groups",)
    search_fields = ("email", "full_name")
    ordering = ("email",)
    readonly_fields = ("last_login", "date_joined", "updated_at")
    filter_horizontal = ("groups", "user_permissions")
