"""
Public admission enquiries (spec 1: "Admission enquiry/contact option").

Like Labe1's leads: the public form only STORES a request. It never creates a
login or a student; an admin follows up and, if the family joins, admits the
student through the normal admission form and links the enquiry to it.
"""

from django.conf import settings
from django.db import models

from apps.academics.models import Board, Standard
from apps.common.models import GlobalTimeStampedModel
from apps.students.models import StudentProfile


class AdmissionEnquiry(GlobalTimeStampedModel):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        ACCEPTED = "ACCEPTED", "Admitted"
        REJECTED = "REJECTED", "Not proceeding"

    class Source(models.TextChoices):
        WEBSITE = "WEBSITE", "Website form"
        WALK_IN = "WALK_IN", "Walk-in"
        PHONE = "PHONE", "Phone call"
        REFERRAL = "REFERRAL", "Referral"

    parent_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=16, db_index=True)
    email = models.EmailField(blank=True)
    student_name = models.CharField(max_length=150)
    standard = models.ForeignKey(
        Standard, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    board = models.ForeignKey(
        Board, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    medium = models.CharField(
        max_length=10, choices=StudentProfile.Medium.choices, blank=True
    )
    school_name = models.CharField(
        max_length=200, blank=True, help_text="As the family gave it (free text)."
    )
    message = models.TextField(blank=True)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.WEBSITE, db_index=True
    )

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.NEW, db_index=True
    )
    notes = models.TextField(blank=True, help_text="Admin-only follow-up notes.")
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    student = models.ForeignKey(
        "students.StudentProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Set when the enquiry turned into an admission.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Staff member who recorded it (walk-in / phone); empty for the website form.",
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        db_table = "admission_enquiries"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.student_name} ({self.parent_name}, {self.status})"
