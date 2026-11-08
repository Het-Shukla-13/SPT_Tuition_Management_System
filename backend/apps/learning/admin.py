from django.contrib import admin

from apps.learning.models import (
    DocumentFile,
    Note,
    NoteAssignment,
    TestAssignment,
    TestPaper,
)


@admin.register(TestPaper)
class TestPaperAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "board",
        "standard",
        "subject",
        "academic_year",
        "is_archived",
    ]
    list_filter = ["board", "standard", "subject", "is_archived"]
    search_fields = ["title"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "board",
        "standard",
        "subject",
        "academic_year",
        "is_archived",
    ]
    list_filter = ["board", "standard", "subject", "is_archived"]
    search_fields = ["title"]


@admin.register(DocumentFile)
class DocumentFileAdmin(admin.ModelAdmin):
    """Read-only. Files are uploaded and served through the API (permission checks)."""

    list_display = ["kind", "version", "original_name", "is_current", "uploaded_at"]
    exclude = ["file"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(TestAssignment)
class TestAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        "test_paper",
        "student",
        "test_starts_at",
        "marks_obtained",
        "revoked_at",
    ]


@admin.register(NoteAssignment)
class NoteAssignmentAdmin(admin.ModelAdmin):
    list_display = ["note", "student", "assigned_at", "revoked_at"]
