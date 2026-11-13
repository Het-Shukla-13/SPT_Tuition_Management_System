"""
Students (spec section 4) - design: docs/plans/phase-2-core-data.md.

- StudentProfile is the child as a person. It is NOT a login.
- StudentAccess links logins (parents or the student themself) to students:
  one login can see several students, one student can be seen by several
  logins ("Netflix profiles"). Unlinking keeps the history.
- StudentSubject and StudentAcademicHistory keep what changed and when, so
  changing standard/school/subjects never erases the past (spec edge cases).
"""

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.academics.models import AcademicYear, Board, School, Standard, Subject
from apps.common.models import (
    AbstractTimeStampedModel,
    GlobalTimeStampedModel,
    SoftDeleteManager,
)


def student_photo_path(instance, filename: str) -> str:
    # Random file name: the original name is never trusted or exposed.
    return f"students/photos/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class StudentProfile(AbstractTimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On hold"
        LEFT = "LEFT", "Left the institute"
        COMPLETED = "COMPLETED", "Course completed"

    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"

    class Medium(models.TextChoices):
        ENGLISH = "ENGLISH", "English"
        GUJARATI = "GUJARATI", "Gujarati"
        HINDI = "HINDI", "Hindi"

    admission_number = models.CharField(max_length=20, unique=True, editable=False)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    photo = models.ImageField(upload_to=student_photo_path, null=True, blank=True)

    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True)
    medium = models.CharField(
        max_length=10,
        choices=Medium.choices,
        blank=True,
        db_index=True,
        help_text="Medium of instruction at school.",
    )
    address = models.TextField(blank=True)

    # Contact on file for the institute to call. This is NOT a login.
    guardian_name = models.CharField(max_length=150, blank=True)
    guardian_relation = models.CharField(max_length=50, blank=True)
    guardian_phone = models.CharField(max_length=16, blank=True, db_index=True)
    guardian_email = models.EmailField(blank=True)

    # Current academic placement (history in StudentAcademicHistory).
    board = models.ForeignKey(Board, on_delete=models.PROTECT, related_name="students")
    standard = models.ForeignKey(
        Standard, on_delete=models.PROTECT, related_name="students"
    )
    school = models.ForeignKey(
        School, on_delete=models.PROTECT, related_name="students"
    )
    admission_date = models.DateField(default=timezone.localdate)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    left_on = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, help_text="Admin-only notes.")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        db_table = "student_profiles"
        ordering = ["first_name", "last_name"]
        indexes = [
            models.Index(
                fields=["last_name", "first_name"], name="student_profiles_name_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.full_name} ({self.admission_number})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class AdmissionSequence(models.Model):
    """Per-year counter for admission numbers, row-locked so numbers never repeat."""

    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "admission_sequences"

    def __str__(self) -> str:
        return f"{self.year}: {self.last_number}"


class StudentAccess(models.Model):
    """Which login can see which student. Revoking keeps the row (history)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_access",
    )
    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="access_links"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    granted_at = models.DateTimeField(default=timezone.now)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "student_access"
        ordering = ["-granted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "student"],
                condition=Q(revoked_at__isnull=True),
                name="student_access_one_active_link",
            ),
        ]

    def __str__(self) -> str:
        return f"user {self.user_id} -> student {self.student_id}"


class StudentSubject(models.Model):
    """A subject the student studies at the institute, from started_on to ended_on."""

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="subjects"
    )
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name="+")
    started_on = models.DateField(default=timezone.localdate)
    ended_on = models.DateField(null=True, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "student_subjects"
        ordering = ["subject__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "subject"],
                condition=Q(ended_on__isnull=True),
                name="student_subjects_one_active",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id}: {self.subject_id}"


class StudentAcademicHistory(GlobalTimeStampedModel):
    class Reason(models.TextChoices):
        ADMISSION = "ADMISSION", "Admission"
        PROMOTION = "PROMOTION", "Promotion to the next standard"
        REPEAT = "REPEAT", "Repeating the same standard"
        SCHOOL_CHANGE = "SCHOOL_CHANGE", "Changed school"
        BOARD_CHANGE = "BOARD_CHANGE", "Changed board"
        CORRECTION = "CORRECTION", "Correction of a mistake"

    student = models.ForeignKey(
        StudentProfile, on_delete=models.CASCADE, related_name="academic_history"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="+"
    )
    board = models.ForeignKey(Board, on_delete=models.PROTECT, related_name="+")
    standard = models.ForeignKey(Standard, on_delete=models.PROTECT, related_name="+")
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name="+")
    started_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True, help_text="Null = current.")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        db_table = "student_academic_history"
        ordering = ["-started_on", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(ended_on__isnull=True),
                name="student_academic_history_one_current",
            ),
        ]
