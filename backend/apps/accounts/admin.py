from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import OTPChallenge, User, UserSession


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Read-only audit view of logins. End sessions through the API, not here."""

    list_display = [
        "id",
        "user",
        "created_at",
        "last_active_at",
        "expires_at",
        "revoked_at",
        "revoked_reason",
        "ip_address",
    ]
    list_filter = ["revoked_reason"]
    search_fields = ["user__email", "user__phone", "ip_address"]
    exclude = ["session_id", "refresh_token_jti"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    """Read-only audit view. The code hash is never shown."""

    list_display = [
        "id",
        "purpose",
        "channel",
        "identifier",
        "attempts",
        "created_at",
        "expires_at",
        "consumed_at",
        "invalidated_at",
    ]
    list_filter = ["purpose", "channel"]
    search_fields = ["identifier"]
    exclude = ["code_hash"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["-created_at"]
    list_display = ["email", "phone", "role", "is_active", "is_staff", "created_at"]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "phone"]
    readonly_fields = ["id", "created_at", "updated_at", "last_login"]

    fieldsets = (
        (None, {"fields": ("id", "email", "phone", "password")}),
        (
            "Role & status",
            {"fields": ("role", "is_active", "is_staff", "is_superuser")},
        ),
        ("Verification", {"fields": ("email_verified_at", "phone_verified_at")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "phone", "role", "password1", "password2"),
            },
        ),
    )
