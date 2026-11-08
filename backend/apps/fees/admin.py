from django.contrib import admin

from apps.fees.models import FeeStructure, LedgerEntry, StudentFeeAccount


@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ["academic_year", "standard", "total_fee", "is_active"]
    list_filter = ["academic_year__board", "is_active"]


@admin.register(StudentFeeAccount)
class StudentFeeAccountAdmin(admin.ModelAdmin):
    """Read-only: money changes go through the API so the ledger stays auditable."""

    list_display = ["student", "academic_year", "agreed_fee", "opening_balance"]
    search_fields = [
        "student__first_name",
        "student__last_name",
        "student__admission_number",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = [
        "entry_date",
        "entry_type",
        "amount",
        "method",
        "receipt_number",
        "account",
    ]
    list_filter = ["entry_type", "method"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
