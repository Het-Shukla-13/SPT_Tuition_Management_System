"""Tests & notes business logic. Views only validate input and call these."""

import hashlib
import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.http import FileResponse, Http404
from django.utils import timezone
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import record
from apps.common.exceptions import AppException, ConflictError
from apps.learning.models import (
    DocumentFile,
    NoteAssignment,
    TestAssignment,
    TestPaper,
)
from apps.students.models import StudentProfile
from apps.students.services import get_linked_student

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Errors
# ─────────────────────────────────────────────────────────────
class InvalidPDF(AppException):
    default_detail = "The file must be a valid PDF."
    default_code = "INVALID_PDF"


class FileTooLarge(AppException):
    default_detail = "The file is too large."
    default_code = "FILE_TOO_LARGE"


class DuplicateDocument(ConflictError):
    default_detail = "This exact PDF is already uploaded. Send confirm_duplicate: true to upload anyway."
    default_code = "DUPLICATE_DOCUMENT"


class ItemArchived(AppException):
    default_detail = "This item is archived and can't be assigned."
    default_code = "ITEM_ARCHIVED"


class AnswerKeyMissing(AppException):
    status_code = 404
    default_detail = "No answer key is available."
    default_code = "ANSWER_KEY_UNAVAILABLE"


class AnswerKeyLocked(AppException):
    status_code = 403
    default_detail = "The answer key becomes available after the test is over."
    default_code = "ANSWER_KEY_LOCKED"


class MarksOutOfRange(AppException):
    default_detail = "Marks must be between 0 and the paper's maximum marks."
    default_code = "MARKS_OUT_OF_RANGE"


class AssignmentRevoked(AppException):
    default_detail = "This assignment has been revoked."
    default_code = "ASSIGNMENT_REVOKED"


# ─────────────────────────────────────────────────────────────
# PDF validation (spec 10.4: signatures, size, corruption)
# ─────────────────────────────────────────────────────────────
def validate_pdf(upload) -> tuple[str, int]:
    """Return (sha256, size). Rejects oversize, non-PDF (by content) and corrupt files."""
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if upload.size > max_bytes:
        raise FileTooLarge(f"The file is larger than {settings.MAX_UPLOAD_SIZE_MB} MB.")
    upload.seek(0)
    if upload.read(5) != b"%PDF-":
        # Checked by content, not name/extension: a renamed .exe is rejected.
        raise InvalidPDF("This file is not a PDF.")
    upload.seek(0)
    try:
        reader = PdfReader(upload)
        if len(reader.pages) == 0:
            raise InvalidPDF("The PDF has no pages.")
    except (PdfReadError, ValueError, KeyError, TypeError):
        raise InvalidPDF("The PDF is damaged or unreadable.") from None
    upload.seek(0)
    digest = hashlib.sha256()
    for chunk in upload.chunks():
        digest.update(chunk)
    upload.seek(0)
    return digest.hexdigest(), upload.size


def _owner_kwargs(item) -> dict:
    return {"test_paper": item} if isinstance(item, TestPaper) else {"note": item}


def _store_file(
    *, actor: User, item, kind: str, upload, confirm_duplicate: bool
) -> DocumentFile:
    sha, size = validate_pdf(upload)
    if (
        not confirm_duplicate
        and DocumentFile.objects.filter(sha256=sha, kind=kind, is_current=True)
        .exclude(**_owner_kwargs(item))
        .exists()
    ):
        raise DuplicateDocument()

    owner = _owner_kwargs(item)
    current = DocumentFile.objects.select_for_update().filter(
        **owner, kind=kind, is_current=True
    )
    next_version = (
        DocumentFile.objects.filter(**owner, kind=kind).aggregate(v=Max("version"))["v"]
        or 0
    ) + 1
    current.update(is_current=False)  # old versions kept for history
    return DocumentFile.objects.create(
        **owner,
        kind=kind,
        file=upload,
        original_name=(upload.name or "document.pdf")[:255],
        size_bytes=size,
        sha256=sha,
        version=next_version,
        uploaded_by=actor,
    )


def current_file(item, kind: str) -> DocumentFile | None:
    return DocumentFile.objects.filter(
        **_owner_kwargs(item), kind=kind, is_current=True
    ).first()


# ─────────────────────────────────────────────────────────────
# Archive items
# ─────────────────────────────────────────────────────────────
def create_item(
    *, actor, model, data: dict, files: dict, confirm_duplicate=False, ip=None
):
    """files: {kind: upload}. Paper (or note) file required; answer key optional."""
    chapters = data.pop("chapters", [])
    with transaction.atomic():
        item = model.objects.create(**data, uploaded_by=actor)
        item.chapters.set(chapters)
        stored = {}
        for kind, upload in files.items():
            if upload:
                stored[kind] = _store_file(
                    actor=actor,
                    item=item,
                    kind=kind,
                    upload=upload,
                    confirm_duplicate=confirm_duplicate,
                ).version
        record(
            AuditLog.Action.DOCUMENT_UPLOADED,
            actor=actor,
            target=item,
            changes={"files": stored, "title": item.title},
            ip=ip,
        )
    return item


@transaction.atomic
def update_item(*, actor, item, data: dict, ip=None):
    chapters = data.pop("chapters", None)
    diff = {}
    for field, value in data.items():
        if getattr(item, field) != value:
            diff[field] = [str(getattr(item, field)), str(value)]
            setattr(item, field, value)
    if diff:
        item.save(update_fields=[*diff, "updated_at"])
    if chapters is not None:
        item.chapters.set(chapters)
        diff["chapters"] = [c.pk for c in chapters]
    if diff:
        record(
            AuditLog.Action.DOCUMENT_UPDATED,
            actor=actor,
            target=item,
            changes=diff,
            ip=ip,
        )
    return item


@transaction.atomic
def replace_file(*, actor, item, kind: str, upload, confirm_duplicate=False, ip=None):
    doc = _store_file(
        actor=actor,
        item=item,
        kind=kind,
        upload=upload,
        confirm_duplicate=confirm_duplicate,
    )
    record(
        AuditLog.Action.DOCUMENT_REPLACED,
        actor=actor,
        target=item,
        changes={"kind": kind, "version": doc.version},
        ip=ip,
    )
    return doc


@transaction.atomic
def remove_answer_key(*, actor, paper: TestPaper, ip=None):
    updated = DocumentFile.objects.filter(
        test_paper=paper, kind=DocumentFile.Kind.ANSWER_KEY, is_current=True
    ).update(is_current=False)
    if not updated:
        raise AnswerKeyMissing()
    record(
        AuditLog.Action.DOCUMENT_REPLACED,
        actor=actor,
        target=paper,
        changes={"kind": "ANSWER_KEY", "removed": True},
        ip=ip,
    )


@transaction.atomic
def set_archived(*, actor, item, archived: bool, ip=None):
    if item.is_archived == archived:
        return item
    item.is_archived = archived
    item.archived_at = timezone.now() if archived else None
    item.save(update_fields=["is_archived", "archived_at", "updated_at"])
    record(
        AuditLog.Action.DOCUMENT_UPDATED,
        actor=actor,
        target=item,
        changes={"is_archived": archived},
        ip=ip,
    )
    return item


# ─────────────────────────────────────────────────────────────
# Assignments
# ─────────────────────────────────────────────────────────────
def _assignment_model(item):
    return (
        (TestAssignment, "test_paper")
        if isinstance(item, TestPaper)
        else (NoteAssignment, "note")
    )


def assign(
    *, actor, item, student_ids: list[int], extra: dict | None = None, ip=None
) -> dict:
    """
    Bulk assign. Each student succeeds or fails on its own (spec 7.4: report
    which succeeded and which failed). Returns {"assigned": [...], "failed": [...]}.
    """
    if item.is_archived:
        raise ItemArchived()
    model, field = _assignment_model(item)
    students = {s.pk: s for s in StudentProfile.objects.filter(pk__in=student_ids)}
    result = {"assigned": [], "failed": []}
    for sid in dict.fromkeys(student_ids):  # de-duplicate, keep order
        student = students.get(sid)
        if student is None:
            result["failed"].append({"student_id": sid, "reason": "NOT_FOUND"})
            continue
        if not student.is_active:
            result["failed"].append({"student_id": sid, "reason": "STUDENT_NOT_ACTIVE"})
            continue
        try:
            with transaction.atomic():
                assignment = model.objects.create(
                    student=student, **{field: item}, assigned_by=actor, **(extra or {})
                )
                record(
                    AuditLog.Action.ASSIGNMENT_CREATED,
                    actor=actor,
                    target=assignment,
                    changes={field: item.pk, "student": sid},
                    ip=ip,
                )
            result["assigned"].append(
                {"student_id": sid, "assignment_id": assignment.pk}
            )
        except IntegrityError:
            result["failed"].append({"student_id": sid, "reason": "ALREADY_ASSIGNED"})
    return result


def revoke(*, actor, model, assignment_ids: list[int], ip=None) -> dict:
    """Bulk revoke; rows are kept (history). Returns {"revoked": [...], "failed": [...]}."""
    result = {"revoked": [], "failed": []}
    for aid in dict.fromkeys(assignment_ids):
        with transaction.atomic():
            assignment = model.objects.select_for_update().filter(pk=aid).first()
            if assignment is None:
                result["failed"].append({"assignment_id": aid, "reason": "NOT_FOUND"})
                continue
            if assignment.revoked_at:
                result["failed"].append(
                    {"assignment_id": aid, "reason": "ALREADY_REVOKED"}
                )
                continue
            assignment.revoked_at = timezone.now()
            assignment.revoked_by = actor
            assignment.save(update_fields=["revoked_at", "revoked_by"])
            record(
                AuditLog.Action.ASSIGNMENT_REVOKED,
                actor=actor,
                target=assignment,
                ip=ip,
            )
        result["revoked"].append(aid)
    return result


@transaction.atomic
def update_test_assignment(*, actor, assignment: TestAssignment, data: dict, ip=None):
    locked = TestAssignment.objects.select_for_update().get(pk=assignment.pk)
    if locked.revoked_at:
        raise AssignmentRevoked()
    diff = {}
    for field, value in data.items():
        if getattr(locked, field) != value:
            diff[field] = [str(getattr(locked, field)), str(value)]
            setattr(locked, field, value)
    if diff:
        locked.save(update_fields=list(diff))
        record(
            AuditLog.Action.ASSIGNMENT_UPDATED,
            actor=actor,
            target=locked,
            changes=diff,
            ip=ip,
        )
    return locked


@transaction.atomic
def grade(*, actor, assignment: TestAssignment, marks, remarks: str = "", ip=None):
    locked = (
        TestAssignment.objects.select_for_update()
        .select_related("test_paper")
        .get(pk=assignment.pk)
    )
    if locked.revoked_at:
        raise AssignmentRevoked()
    maximum = locked.test_paper.max_marks
    if marks is not None and (marks < 0 or (maximum is not None and marks > maximum)):
        raise MarksOutOfRange(f"Marks must be between 0 and {maximum}.")
    old = locked.marks_obtained
    locked.marks_obtained = marks
    locked.grade_remarks = remarks
    locked.graded_by = actor
    locked.graded_at = timezone.now()
    locked.save(
        update_fields=["marks_obtained", "grade_remarks", "graded_by", "graded_at"]
    )
    record(
        AuditLog.Action.ASSIGNMENT_GRADED,
        actor=actor,
        target=locked,
        changes={"marks": [str(old), str(marks)]},
        ip=ip,
    )
    return locked


# ─────────────────────────────────────────────────────────────
# Secure file delivery (spec 10.4)
# ─────────────────────────────────────────────────────────────
def file_response(
    doc: DocumentFile, *, inline: bool, actor=None, ip=None
) -> FileResponse:
    """Stream a stored PDF after the caller has checked permission. Never a public URL."""
    try:
        handle = doc.file.open("rb")
    except FileNotFoundError:
        logger.error("Stored file missing: document_file_id=%s", doc.pk)
        raise Http404 from None
    if actor is not None:
        record(
            AuditLog.Action.FILE_ACCESSED,
            actor=actor,
            target=doc,
            changes={"kind": doc.kind, "version": doc.version},
            ip=ip,
        )
    response = FileResponse(
        handle,
        as_attachment=not inline,
        filename=doc.original_name,
        content_type="application/pdf",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


# ─────────────────────────────────────────────────────────────
# Portal (parents / students)
# ─────────────────────────────────────────────────────────────
def portal_student(user, student_id: int) -> StudentProfile:
    """Linked student only (404 otherwise). Tests/notes need an ACTIVE student."""
    student = get_linked_student(user, student_id)
    return student


def portal_test_assignments(student: StudentProfile):
    if not student.is_active:
        return TestAssignment.objects.none()
    return (
        TestAssignment.objects.filter(student=student, revoked_at__isnull=True)
        .select_related(
            "test_paper__subject", "test_paper__standard", "test_paper__board"
        )
        .prefetch_related(
            Prefetch(
                "test_paper__files",
                queryset=DocumentFile.objects.filter(
                    kind=DocumentFile.Kind.ANSWER_KEY, is_current=True
                ),
                to_attr="current_answer_keys",
            )
        )
    )


def portal_note_assignments(student: StudentProfile):
    if not student.is_active:
        return NoteAssignment.objects.none()
    return NoteAssignment.objects.filter(
        student=student, revoked_at__isnull=True
    ).select_related("note__subject", "note__standard", "note__board")


def portal_test_file(assignment: TestAssignment, kind: str) -> DocumentFile:
    if kind == DocumentFile.Kind.ANSWER_KEY:
        doc = current_file(assignment.test_paper, DocumentFile.Kind.ANSWER_KEY)
        if doc is None:
            raise AnswerKeyMissing()
        if not assignment.answer_key_unlocked:
            raise AnswerKeyLocked()
        return doc
    doc = current_file(assignment.test_paper, DocumentFile.Kind.PAPER)
    if doc is None:
        raise Http404
    return doc
