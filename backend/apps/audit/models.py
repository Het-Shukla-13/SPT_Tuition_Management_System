"""
Append-only record of sensitive actions (spec section 10.6).

Who did what to which record, when, from where. Rows are never edited or
deleted through the application. Never store OTPs, passwords or tokens here.
"""

from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        USER_ROLE_CHANGED = "USER_ROLE_CHANGED", "User role changed"
        USER_DEACTIVATED = "USER_DEACTIVATED", "User deactivated"
        USER_ACTIVATED = "USER_ACTIVATED", "User activated"
        USER_INVITED = "USER_INVITED", "Login created (invited)"
        USER_UPDATED = "USER_UPDATED", "User details updated"
        GOOGLE_LINKED = "GOOGLE_LINKED", "Google account linked"
        GOOGLE_UNLINKED = "GOOGLE_UNLINKED", "Google account unlinked"
        CONTACT_CHANGED = "CONTACT_CHANGED", "Email/phone added or changed"
        CONTACT_REMOVED = "CONTACT_REMOVED", "Email/phone removed"
        STUDENT_ADMITTED = "STUDENT_ADMITTED", "Student admitted"
        STUDENT_UPDATED = "STUDENT_UPDATED", "Student details updated"
        STUDENT_ACADEMIC_CHANGED = (
            "STUDENT_ACADEMIC_CHANGED",
            "Board/standard/school changed",
        )
        STUDENT_STATUS_CHANGED = "STUDENT_STATUS_CHANGED", "Student status changed"
        STUDENT_SUBJECTS_CHANGED = (
            "STUDENT_SUBJECTS_CHANGED",
            "Student subjects changed",
        )
        STUDENT_ACCESS_GRANTED = (
            "STUDENT_ACCESS_GRANTED",
            "Login given access to a student",
        )
        STUDENT_ACCESS_REVOKED = (
            "STUDENT_ACCESS_REVOKED",
            "Login's access to a student removed",
        )

    action = models.CharField(max_length=64, choices=Action.choices, db_index=True)
    # SET_NULL: the trail must survive even if an account row is ever removed.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    target_type = models.CharField(max_length=64, help_text="e.g. 'accounts.User'")
    target_id = models.CharField(max_length=64, db_index=True)
    changes = models.JSONField(
        default=dict, blank=True, help_text='e.g. {"role": ["PORTAL", "ADMIN"]}'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    request_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["target_type", "target_id"], name="audit_logs_target_idx"
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.action} on {self.target_type}#{self.target_id} by {self.actor_id}"
        )
