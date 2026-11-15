from django.contrib import admin

from apps.learning.models import (
    DocumentFile,
    Note,
    NoteAssignment,
    TestAssignment,
    TestPaper,
)


class _BoardsColumn:
    @admin.display(description="Boards")
    def board_list(self, obj):
        return ", ".join(b.code for b in obj.boards.all()) or "All boards"


@admin.register(TestPaper)
class TestPaperAdmin(_BoardsColumn, admin.ModelAdmin):
    list_display = [
        "title",
        "board_list",
        "standard",
        "subject",
        "academic_year_name",
        "is_archived",
    ]
    list_filter = ["boards", "standard", "subject", "is_archived"]
    search_fields = ["title"]


@admin.register(Note)
class NoteAdmin(_BoardsColumn, admin.ModelAdmin):
    list_display = [
        "title",
        "board_list",
        "standard",
        "subject",
        "academic_year_name",
        "is_archived",
    ]
    list_filter = ["boards", "standard", "subject", "is_archived"]
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
