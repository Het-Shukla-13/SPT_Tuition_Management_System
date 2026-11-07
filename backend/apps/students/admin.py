from django.contrib import admin

from apps.students.models import (
    StudentAcademicHistory,
    StudentAccess,
    StudentProfile,
    StudentSubject,
)


class StudentSubjectInline(admin.TabularInline):
    model = StudentSubject
    extra = 0
    readonly_fields = ["subject", "started_on", "ended_on", "changed_by"]
    can_delete = False


class StudentAccessInline(admin.TabularInline):
    model = StudentAccess
    fk_name = "student"
    extra = 0
    readonly_fields = ["user", "granted_by", "granted_at", "revoked_by", "revoked_at"]
    can_delete = False


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    """Read-mostly: use the API so history, audit and invites stay consistent."""

    list_display = [
        "admission_number",
        "first_name",
        "last_name",
        "standard",
        "board",
        "status",
    ]
    list_filter = ["status", "board", "standard"]
    search_fields = ["admission_number", "first_name", "last_name", "guardian_phone"]
    readonly_fields = [
        "admission_number",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
    ]
    inlines = [StudentSubjectInline, StudentAccessInline]

    def has_add_permission(self, request):
        return False


@admin.register(StudentAcademicHistory)
class StudentAcademicHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "student",
        "academic_year",
        "board",
        "standard",
        "school",
        "started_on",
        "ended_on",
        "reason",
    ]
    list_filter = ["reason", "academic_year"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
