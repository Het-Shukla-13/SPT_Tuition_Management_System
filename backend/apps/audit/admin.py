from django.contrib import admin

from apps.audit.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only. Audit entries are never edited or deleted from the UI."""

    list_display = [
        "created_at",
        "action",
        "actor",
        "target_type",
        "target_id",
        "ip_address",
    ]
    list_filter = ["action", "target_type"]
    search_fields = ["target_id", "actor__email", "request_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
