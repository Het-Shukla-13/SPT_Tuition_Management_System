from django.contrib import admin

from apps.academics.models import (
    AcademicYear,
    Board,
    Chapter,
    School,
    Standard,
    Subject,
)


@admin.register(Board)
class BoardAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "is_active"]
    list_filter = ["is_active"]


@admin.register(Standard)
class StandardAdmin(admin.ModelAdmin):
    list_display = ["level", "name", "is_active"]
    list_filter = ["is_active"]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    list_filter = ["is_active"]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ["board", "standard", "subject", "number", "name", "is_active"]
    list_filter = ["board", "standard", "subject", "is_active"]
    search_fields = ["name"]


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "board", "is_active"]
    list_filter = ["board", "is_active"]
    search_fields = ["name", "city"]


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = [
        "board",
        "name",
        "start_date",
        "end_date",
        "is_current",
        "is_active",
    ]
    list_filter = ["board", "is_current"]
