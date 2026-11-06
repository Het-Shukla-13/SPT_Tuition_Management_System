"""
Abstract base models reused by every app (mirrors Labe1's common models).

Primary keys are Django's default auto-increment integers
(DEFAULT_AUTO_FIELD = BigAutoField). Access to records is protected by
permission checks, never by the ID being hard to guess.
"""

from django.db import models
from django.utils import timezone


class GlobalTimeStampedModel(models.Model):
    """Abstract base with created_at / updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AbstractTimeStampedModel(GlobalTimeStampedModel):
    """
    Timestamps + soft delete.

    Records with history (students, payments, assignments...) are never
    physically removed: `soft_delete()` flags them so they disappear from
    normal queries while financial/academic history stays intact.
    """

    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self) -> None:
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class SoftDeleteManager(models.Manager):
    """Default manager that hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)
