"""
Tests & notes (spec parts 3-5). Design: docs/plans/phase-3-tests-notes.md.

- TestPaper / Note: the archive items (metadata).
- DocumentFile: the PDFs. Replacing a PDF adds a new version; old ones are
  kept, and students always get the current one.
- TestAssignment / NoteAssignment: which student got what. Revoking keeps
  the row (history); one ACTIVE assignment per student + item.
- Answer keys unlock for students automatically once the test is over
  (test_starts_at + duration_minutes). No time set = never.
"""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import (
    AcademicYear,
    Board,
    Chapter,
    School,
    Standard,
    Subject,
)
from apps.common.models import GlobalTimeStampedModel
from apps.students.models import StudentProfile


class Semester(models.IntegerChoices):
    FIRST = 1, "Semester 1"
    SECOND = 2, "Semester 2"


class _LearningItem(GlobalTimeStampedModel):
    """Shared metadata of a test paper or a note."""

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    board = models.ForeignKey(Board, on_delete=models.PROTECT, related_name="+")
    standard = models.ForeignKey(Standard, on_delete=models.PROTECT, related_name="+")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    chapters = models.ManyToManyField(Chapter, blank=True, related_name="+")
    semester = models.PositiveSmallIntegerField(
        choices=Semester.choices, null=True, blank=True
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="+"
    )
    remarks = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # Archived = hidden from the archive and can't be newly assigned. Existing
    # assignments stay meaningful (spec: "test deleted - history remains").
    is_archived = models.BooleanField(default=False, db_index=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def __str__(self) -> str:
        return self.title


class TestPaper(_LearningItem):
    __test__ = False  # not a pytest test class (name starts with "Test")

    school = models.ForeignKey(
        School,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="If the paper is specific to one school.",
    )
    test_date = models.DateField(
        null=True, blank=True, help_text="Planned date, informational."
    )
    max_marks = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    duration_minutes = models.PositiveIntegerField(
        default=60, help_text="Default test length; each assignment can override it."
    )

    class Meta:
        db_table = "test_papers"
        ordering = ["-created_at"]


class Note(_LearningItem):
    class Meta:
        db_table = "notes"
        ordering = ["-created_at"]


def document_upload_path(instance, filename: str) -> str:
    # Random name: never trust or expose the uploaded file name in storage.
    return f"documents/{instance.kind.lower()}/{uuid.uuid4().hex}.pdf"


class DocumentFile(models.Model):
    class Kind(models.TextChoices):
        PAPER = "PAPER", "Test paper"
        ANSWER_KEY = "ANSWER_KEY", "Answer key"
        NOTE = "NOTE", "Notes"

    test_paper = models.ForeignKey(
        TestPaper, on_delete=models.PROTECT, null=True, blank=True, related_name="files"
    )
    note = models.ForeignKey(
        Note, on_delete=models.PROTECT, null=True, blank=True, related_name="files"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices)
    file = models.FileField(upload_to=document_upload_path, max_length=255)
    original_name = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    version = models.PositiveIntegerField()
    is_current = models.BooleanField(default=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "document_files"
        ordering = ["-version"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(test_paper__isnull=False, note__isnull=True)
                    | Q(test_paper__isnull=True, note__isnull=False)
                ),
                name="document_files_exactly_one_owner",
            ),
            models.UniqueConstraint(
                fields=["test_paper", "kind"],
                condition=Q(is_current=True),
                name="document_files_one_current_per_paper_kind",
            ),
            models.UniqueConstraint(
                fields=["note", "kind"],
                condition=Q(is_current=True),
                name="document_files_one_current_per_note_kind",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.kind} v{self.version} ({self.original_name})"


class _Assignment(models.Model):
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="+"
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class TestAssignment(_Assignment):
    __test__ = False  # not a pytest test class

    test_paper = models.ForeignKey(
        TestPaper, on_delete=models.PROTECT, related_name="assignments"
    )
    test_starts_at = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    marks_obtained = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True
    )
    grade_remarks = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "test_assignments"
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "test_paper"],
                condition=Q(revoked_at__isnull=True),
                name="test_assignments_one_active",
            ),
        ]

    def __str__(self) -> str:
        return f"test {self.test_paper_id} -> student {self.student_id}"

    @property
    def test_ends_at(self):
        if self.test_starts_at is None:
            return None
        minutes = self.duration_minutes or self.test_paper.duration_minutes
        return self.test_starts_at + timedelta(minutes=minutes)

    @property
    def answer_key_unlocked(self) -> bool:
        ends = self.test_ends_at
        return ends is not None and timezone.now() >= ends


class NoteAssignment(_Assignment):
    note = models.ForeignKey(Note, on_delete=models.PROTECT, related_name="assignments")

    class Meta:
        db_table = "note_assignments"
        ordering = ["-assigned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "note"],
                condition=Q(revoked_at__isnull=True),
                name="note_assignments_one_active",
            ),
        ]

    def __str__(self) -> str:
        return f"note {self.note_id} -> student {self.student_id}"
